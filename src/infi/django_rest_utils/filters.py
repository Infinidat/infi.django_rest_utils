from builtins import str
from past.builtins import basestring
from builtins import object
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.template.loader import render_to_string
from django.db.models import Q

import re

from rest_framework import filters
from rest_framework.exceptions import ValidationError
from collections import OrderedDict


DEFAULT_IGNORE = [
    settings.REST_FRAMEWORK['ORDERING_PARAM'],
    'fields',
    'page',
    'page_size',
    'format',
    'q',
    'stream',
]

class FilterableField(object):
    '''
    Describes a field that can be filtered on.
    name - the field name to use in the API.
    source - the field name in the model, in case it is different than the name.
             it can also be a callable f(field, orm_operator, value) --> Q object
    converter - an optional function to modify the given filter value before passing it to the queryset.
    datatype - the type of values that are expected for this field.
    advanced - if true, the filter will be used only by InfinidatFilter and not by SimpleFilter
    '''

    STRING   = 'string'
    INTEGER  = 'integer'
    FLOAT    = 'float'
    BOOLEAN  = 'boolean'
    DATETIME = 'datetime'

    def __init__(self, name, source=None, converter=None, datatype=STRING, advanced=False):
        self.name = name
        self.source = source or name
        self.converter = converter or (lambda value: value)
        self.datatype = datatype
        self.advanced = advanced

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return '<FilterableField name=%s source=%s datatype=%s>' % (self.name, self.source, self.datatype)

    def convert(self, value):
        if isinstance(value, list):
            return [self.converter(v) for v in value]
        else:
            return self.converter(value)

    def build_q(self, orm_operator, value):
        value = self.convert(value)
        if hasattr(self.source, '__call__'):
            return self.source(self, orm_operator, value)
        return Q(**{self.source + '__' + orm_operator: value})

    @classmethod
    def for_model(cls, model_cls):
        '''
        Generate a list of filterable fields automatically for the given model class.
        Includes model fields of the following types: CharField, TextField, IntegerField, AutoField,
        DateField, DateTimeField, FloatField, DecimalField, BooleanField, NullBooleanField.
        '''
        from django.db.models.fields import CharField, TextField, IntegerField, AutoField, DateField, DateTimeField
        from django.db.models.fields import FloatField, DecimalField, BooleanField, NullBooleanField
        filterable_fields = []
        for field in model_cls._meta.get_fields():
            datatype = None
            if isinstance(field, CharField) or isinstance(field, TextField):
                datatype = FilterableField.STRING
            elif isinstance(field, IntegerField) or isinstance(field, AutoField):
                datatype = FilterableField.INTEGER
            elif isinstance(field, FloatField) or isinstance(field, DecimalField):
                datatype = FilterableField.FLOAT
            elif isinstance(field, BooleanField) or isinstance(field, NullBooleanField):
                datatype = FilterableField.BOOLEAN
            elif isinstance(field, DateField) or isinstance(field, DateTimeField):
                datatype = FilterableField.DATETIME
            if datatype:
                filterable_fields.append(cls(field.name, datatype=datatype))
        return filterable_fields


class Operator(object):

    def __init__(self, name, orm_operator, description='', negate=False, min_vals=1, max_vals=1, boolean=False):
        self.name = name
        self.orm_operator = orm_operator
        self.description = description
        self.negate = negate
        self.min_vals = min_vals
        self.max_vals = max_vals
        self.boolean = boolean

    def __unicode__(self):
        return self.name

    def get_expected_value_description(self):
        if self.boolean:
            return 'a single boolean value: 0 or 1'
        if self.max_vals == 1:
            return 'a single value'
        if self.max_vals == self.min_vals:
            return 'a list of exactly {} values'.format(self.max_vals)
        return 'a list of {}-{} values'.format(self.min_vals, self.max_vals)


def _get_filterable_fields(view):
    '''
    Get the list of filterable fields for the given view, or deduce them
    from the serializer fields.
    '''
    serializer = view.get_serializer()
    if hasattr(serializer, 'get_filterable_fields'):
        return serializer.get_filterable_fields()
    # Autodetect filterable fields
    return [
        FilterableField(field.source or field_name, datatype=_get_field_type(field))
        for field_name, field in serializer.fields.items()
        if not getattr(field, 'write_only', False) and not field.source == '*'
    ]


def _get_field_type(serializer_field):
    '''
    Determine the appropriate FilterableField type for the given serializer field.
    '''
    from rest_framework.fields import BooleanField, IntegerField, FloatField, DecimalField, DateTimeField
    if isinstance(serializer_field, BooleanField):
        return FilterableField.BOOLEAN
    if isinstance(serializer_field, IntegerField):
        return FilterableField.INTEGER
    if isinstance(serializer_field, FloatField) or isinstance(serializer_field, DecimalField):
        return FilterableField.FLOAT
    if isinstance(serializer_field, DateTimeField):
        return FilterableField.DATETIME
    return FilterableField.STRING


def _parse_array(expr):
    '''
    Parse an array expression such as "a,b" or "[1,2,3]"
    '''
    expr = expr.strip()
    if (expr.startswith('(') and expr.endswith(')')) or expr.startswith('[') and expr.endswith(']'):
        expr = expr[1:-1]
    if not expr:
        return []
    return [x.strip() for x in expr.split(',')]


def _normalize_query(query_string,
                    findterms=re.compile(r'"([^"]+)"|(\S+)').findall,
                    normspace=re.compile(r'\s{2,}').sub):
    '''
    Splits the query string in invidual keywords, getting rid of unecessary spaces
    and grouping quoted words together.
    Example:
    >>> normalize_query('  some random  words "with   quotes  " and   spaces')
    ['some', 'random', 'words', 'with quotes', 'and', 'spaces']
    '''
    return [normspace(' ', (t[0] or t[1]).strip()) for t in findterms(query_string)]


class InfinidatFilter(filters.BaseFilterBackend):
    '''
    Implements a filter backend that uses Infinidat's API syntax.
    The serializer in use can implement get_filterable_fields that
    returns a list of FilterableField instances. If not, the list
    will be generated automatically from the serializer fields.
    '''

    def get_filter_description(self, view, html):
        if not html:
            return None
        filterable_fields = _get_filterable_fields(view)
        if not filterable_fields:
            return None
        operators = self._get_operators()
        active_filters = [(f.name, view.request.GET[f.name]) for f in filterable_fields if f.name in view.request.GET]
        context = dict(
            fields=filterable_fields,
            operators=operators,
            active_filters=active_filters,
            url=view.request.build_absolute_uri(view.request.path)
        )
        return render_to_string('django_rest_utils/infinidat_filter.html', context)

    def filter_queryset(self, request, queryset, view):
        filterable_fields = _get_filterable_fields(view)
        ignored_fields = self._get_ignored_fields(view)
        for field_name in request.GET.keys():
            if field_name in ignored_fields:
                continue
            field = None
            for f in filterable_fields:
                if field_name == f.name:
                    field = f
                    break
            if not field:
                names = [f.name for f in filterable_fields]
                raise ValidationError("Unknown filter field: '%s' (choices are %s)" % (field_name, ', '.join(names)))
            for expr in request.GET.getlist(field_name):
                queryset = self._apply_filter(queryset, field, expr)
        return queryset

    def _get_ignored_fields(self, view):
        return getattr(view, 'non_filtering_fields', DEFAULT_IGNORE)

    def _get_operators(self):
        return [
            Operator('eq',      'exact',     'field = value'),
            Operator('ne',      'exact',     'field <> value', negate=True),
            Operator('lt',      'lt',        'field < value'),
            Operator('le',      'lte',       'field <= value'),
            Operator('gt',      'gt',        'field > value'),
            Operator('ge',      'gte',       'field >= value'),
            Operator('like',    'icontains', 'field contains a string (case insensitive)'),
            Operator('unlike',  'icontains', 'field does not contain a string (case insensitive)', negate=True),
            Operator('in',      'in',        'field is equal to one of the given values', max_vals=1000),
            Operator('out',     'in',        'field is not equal to any of the given values', negate=True, max_vals=1000),
            Operator('between', 'range',     'field is in a range of two values (inclusive)', min_vals=2, max_vals=2),
            Operator('isnull',  'isnull',    'field is null', boolean=True),
        ]

    def _apply_filter(self, queryset, field, expr):
        q, negate = self._build_q(field, expr)
        try:
            return queryset.exclude(q).distinct() if negate else queryset.filter(q).distinct()
        except (ValueError, DjangoValidationError):
            raise ValidationError(field.name + ': the given operator or value are inappropriate for this field')

    def _build_q(self, field, expr):
        # Get operator and value
        operators = self._get_operators()
        if ':' in expr:
            opname, value = expr.split(':', 1)
            try:
                [operator] = [operator for operator in operators if operator.name == opname]
            except ValueError:
                raise ValidationError('{}: unknown operator "{}"'.format(field.name, opname))
        else:
            operator = operators[0] # First operator is the default one
            value = expr
        # Build Q object
        if operator.max_vals > 1:
            vals = _parse_array(value)
            # Validate that the correct number of values is provided
            if len(vals) < operator.min_vals or len(vals) > operator.max_vals:
                raise ValidationError('{}: "{}" operator expects {}'.format(
                                      field.name, operator.name, operator.get_expected_value_description()))
            q = field.build_q(operator.orm_operator, vals)
        else:
            if operator.boolean:
                try:
                    value = int(value)
                except ValueError:
                    raise ValidationError('{}: "{}" operator expects {}'.format(
                                          field.name, operator.name, operator.get_expected_value_description()))
            q = field.build_q(operator.orm_operator, value)

        return (q, operator.negate)


class SimpleFilter(object):

    def get_filter_description(self, view, html):
        if not html:
            return None
        filterable_fields = [f for f in _get_filterable_fields(view)
                             if f.datatype in (FilterableField.STRING, FilterableField.INTEGER)
                             and not f.advanced]
        if not filterable_fields:
            return None
        context = dict(
            fields=filterable_fields,
            url=view.request.build_absolute_uri(view.request.path),
            terms=view.request.GET.get('q', '')
        )
        return render_to_string('django_rest_utils/simple_filter.html', context)

    def filter_queryset(self, request, queryset, view):
        terms = _normalize_query(request.GET.get('q', ''))
        if terms:
            filterable_fields = _get_filterable_fields(view)
            query = None
            for term in terms:
                numeric = term.isdigit()
                or_query = None # Query to search for a given term in each field
                for field in filterable_fields:
                    if field.advanced:
                        continue
                    try:
                        if field.datatype == FilterableField.STRING:
                            q = field.build_q('icontains', term)
                        elif field.datatype == FilterableField.INTEGER and numeric:
                            q = field.build_q('exact', term)
                        else:
                            continue
                        or_query = or_query | q if or_query else q
                    except ValidationError:
                        pass
                query = query & or_query if query else or_query
            queryset = queryset.filter(query) if query else queryset.none()
        return queryset


class OrderingField(object):
    '''
    Describes a field that can be used in ordering the queryset.
    name - the field name to use in the API.
    sources - the field name(s) or expression(s) in the model, in case it is different than the name.
              this can be a string or a tuple of strings.
    '''

    def __init__(self, name, source=None):
        self.name = name
        self.source = (name,) if source is None else (source, ) if isinstance(source, basestring) else tuple(source)

    def get_terms(self, descending_order=False):
        '''
        Get a list of terms to order the queryset by
        '''
        if descending_order:
            return ['-' + s for s in self.source]
        else:
            return list(self.source)

    @classmethod
    def for_model(cls, model_cls):
        '''
        Generate a list of ordering fields automatically for the given model class.
        Includes all "simple" model fields, meaning fields that are not relations to other models.
        '''
        from django.db.models.fields.related import RelatedField, ForeignObjectRel
        ordering_fields = []
        for field in model_cls._meta.get_fields():
            if isinstance(field, RelatedField) or isinstance(field, ForeignObjectRel):
                continue
            ordering_fields.append(cls(field.name))
        return ordering_fields



class OrderingFilter(filters.OrderingFilter):
    '''
    A subclass of the default OrderingFilter that provides an implementation of get_filter_description.
    '''

    def get_filter_description(self, view, html):
        if not html:
            return None
        ordering_fields = self.get_ordering_fields(view)
        if not ordering_fields:
            return None
        # take the ordering params from request and send it to the template in order to populate the sorting inputs - #sptl 567
        ordering = None
        params = view.request.query_params.get(self.ordering_param)
        if params:
            ordering = [str(param.strip()) for param in params.split(',')]
        context = dict(
            ordering_param=self.ordering_param,
            default_ordering=self.get_default_ordering(view),
            fields=ordering_fields,
            ordering=ordering,
            url=view.request.build_absolute_uri(view.request.path)
        )
        return render_to_string('django_rest_utils/ordering_filter.html', context)


    def get_ordering_fields(self, view):
        '''
        Returns a list of OrderingField instances.
        '''
        # Try to get fields from the view or this filter
        sortable_fields = getattr(view, 'ordering_fields', self.ordering_fields)
        if sortable_fields is None:
            # Try to get fields from the serializer
            serializer = view.get_serializer()
            sortable_fields = getattr(serializer, 'get_ordering_fields', lambda: None)()
            if sortable_fields is None:
                # Autodetect fields
                sortable_fields = [
                    OrderingField(field.source or field_name)
                    for field_name, field in serializer.fields.items()
                    if not getattr(field, 'write_only', False) and not field.source == '*'
                ]
        else:
            sortable_fields = [OrderingField(name) for name in sortable_fields]
        return sortable_fields

    def remove_invalid_fields(self, queryset, fields, view, request):
        ret = []
        ordering_fields_dict = {f.name: f for f in self.get_ordering_fields(view)}
        for field in fields:
            descending_order = (field[0] == '-')
            name = field[1:] if descending_order else field
            ordering_field = ordering_fields_dict.get(name)
            if ordering_field:
                ret += ordering_field.get_terms(descending_order)
        return ret

    def filter_queryset(self, request, queryset, view):
        # Overridden to always sort also by the primary key field.
        # This ensures that the order is unique, allowing to get consistent pagination.
        # See http://www.postgresql.org/docs/9.3/static/queries-limit.html
        ordering = self.get_ordering(request, queryset, view) or []
        pk_field = queryset.model._meta.pk.name
        if not any(field in ordering for field in (pk_field, '-' + pk_field, 'pk', '-pk')):
            ordering.append(pk_field)
        return queryset.extra(order_by=ordering)
