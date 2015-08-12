from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.template.loader import render_to_string
from django.db.models import Q

from rest_framework import filters
from rest_framework.exceptions import ValidationError
from rest_framework.compat import OrderedDict


IGNORE = [
    settings.REST_FRAMEWORK['ORDERING_PARAM'],
    'page',
    'page_size',
    'format'
]


class FilterableField(object):
    '''
    Describes a field that can be filtered on.
    name - the field name to use in the API.
    source - the field name in the model, in case it is different than the name.
             it can also be a callable f(field, orm_operator, value) --> Q object
    converter - an optional function to modify the given filter value before passing it to the queryset.
    datatype - the type of values that are expected for this field.
    '''

    STRING   = 'string'
    INTEGER  = 'integer'
    FLOAT    = 'float'
    BOOLEAN  = 'boolean'
    DATETIME = 'datetime'

    def __init__(self, name, source=None, converter=None, datatype=STRING):
        self.name = name
        self.source = source or name
        self.converter = converter or (lambda value: value)
        self.datatype = datatype

    def __unicode__(self):
        return self.name

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


class Operator(object):

    def __init__(self, name, orm_operator, description='', negate=False, min_vals=1, max_vals=1):
        self.name = name
        self.orm_operator = orm_operator
        self.description = description
        self.negate = negate
        self.min_vals = min_vals
        self.max_vals = max_vals

    def __unicode__(self):
        return self.name

    def get_expected_value_description(self):
        if self.max_vals == 1:
            return 'a single value'
        if self.max_vals == self.min_vals:
            return 'a list of exactly {} values'.format(self.max_vals)
        return 'a list of {}-{} values'.format(self.min_vals, self.max_vals)


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
        filterable_fields = self._get_filterable_fields(view)
        if not filterable_fields:
            return None
        operators = self._get_operators()
        return render_to_string('django_rest_utils/infinidat_filter.html',
                                dict(fields=filterable_fields, operators=operators))

    def filter_queryset(self, request, queryset, view):
        filterable_fields = self._get_filterable_fields(view)
        for field_name in request.GET.keys():
            if field_name in IGNORE:
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

    def _get_filterable_fields(self, view):
        serializer = view.get_serializer()
        if hasattr(serializer, 'get_filterable_fields'):
            return serializer.get_filterable_fields()
        # Autodetect filterable fields
        return [
            FilterableField(field.source or field_name, datatype=self._get_field_type(field))
            for field_name, field in serializer.fields.items()
            if not getattr(field, 'write_only', False) and not field.source == '*'
        ]

    def _get_field_type(self, serializer_field):
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
            Operator('between', 'range',     'field is in a range of two values (inclusive)', min_vals=2, max_vals=2)
        ]

    def _apply_filter(self, queryset, field, expr):
        q = self._build_q(field, expr)
        try:
            return queryset.filter(q)
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
            q = field.build_q(operator.orm_operator, value)
        return ~q if operator.negate else q


def _parse_array(expr):
    expr = expr.strip()
    if (expr.startswith('(') and expr.endswith(')')) or expr.startswith('[') and expr.endswith(']'):
        expr = expr[1:-1]
    if not expr:
        return []
    return [x.strip() for x in expr.split(',')]


class OrderingFilter(filters.OrderingFilter):
    '''
    A subclass of the default OrderingFilter that provides an implementation of get_filter_description.
    '''

    def get_filter_description(self, view, html):
        if not html:
            return None
        context = dict(
            ordering_param=self.ordering_param,
            default_ordering=self.get_default_ordering(view),
            fields=self.get_valid_fields(view)
        )
        return render_to_string('django_rest_utils/ordering_filter.html', context)

    def get_valid_fields(self, view):
        valid_fields = getattr(view, 'ordering_fields', self.ordering_fields)
        if valid_fields is None:
            # Default to allowing filtering on serializer fields
            serializer_class = getattr(view, 'serializer_class')
            valid_fields = [
                field.source or field_name
                for field_name, field in serializer_class().fields.items()
                if not getattr(field, 'write_only', False) and not field.source == '*'
            ]
        return valid_fields
