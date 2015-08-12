from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.template.loader import render_to_string
from django.db.models import Q

from rest_framework import filters
from rest_framework.exceptions import ValidationError


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


class InfinidatFilter(filters.BaseFilterBackend):
    '''
    Implements a filter backend that uses Infinidat's API syntax.
    The serializer in use must implement get_filterable_fields that
    returns a list of FilterableField instances.
    '''

    def get_filter_description(self, view, html):
        if not html:
            return None
        filterable_fields = self._get_filterable_fields(view)
        if not filterable_fields:
            return None
        return render_to_string('django_rest_utils/infinidat_filter.html', dict(fields=filterable_fields))

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
            if len(request.GET.getlist(field_name)) > 1:
                raise ValidationError("Filter field '%s' specified more than once" % field_name)
            queryset = self._apply_filter(queryset, field, request.GET[field_name])
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

    def _apply_filter(self, queryset, field, expr):
        # Get operator and value
        if ':' in expr:
            op, value = expr.split(':', 1)
        else:
            op, value = 'eq', expr
        # Get filter kwargs
        kwargs = {}
        revert = False # if True, apply the inverse logic
        if op == 'eq':
            q = field.build_q('exact', value)
        elif op == 'lt':
            q = field.build_q('lt', value)
        elif op == 'le':
            q = field.build_q('lte', value)
        elif op == 'gt':
            q = field.build_q('gt', value)
        elif op == 'ge':
            q = field.build_q('gte', value)
        elif op == 'ne':
            q = ~field.build_q('exact', value)
        elif op == 'like':
            q = field.build_q('icontains', value)
        elif op == 'in':
            vals = _parse_array(value)
            if not vals:
                raise ValidationError(field.name + ': IN filter expects at least one value')
            q = field.build_q('in', vals)
        elif op == 'out':
            vals = _parse_array(value)
            if not vals:
                raise ValidationError(field.name + ': OUT filter expects at least one value')
            q = ~field.build_q('in', vals)
        elif op == 'between':
            vals = [field.convert(val) for val in _parse_array(value)]
            if len(vals) != 2:
                raise ValidationError(field.name + ': BETWEEN filter expects exactly 2 values')
            q = field.build_q('range', vals)
        else:
            raise ValidationError(field.source + ': unknown operator "{}"'.format(op))
        # Apply the filter to the queryset
        try:
            return queryset.filter(q)
        except (ValueError, DjangoValidationError):
            raise ValidationError(field.name + ': the given operator or value are inappropriate for this field')


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
