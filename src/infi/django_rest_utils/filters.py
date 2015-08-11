from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.template.loader import render_to_string

from rest_framework import filters
from rest_framework.exceptions import ValidationError


IGNORE = [
    settings.REST_FRAMEWORK['ORDERING_PARAM'],
    'page',
    'page_size',
    'format'
]


class InfinidatFilter(filters.BaseFilterBackend):

    def get_filter_description(self, view, html):
        if not html:
            return None
        filterable_fields = self._get_filterable_fields(view)
        if not filterable_fields:
            return None
        return render_to_string('django_rest_utils/infinidat_filter.html', dict(fields=filterable_fields))

    def filter_queryset(self, request, queryset, view):
        filterable_fields = self._get_filterable_fields(view)
        for field in request.GET.keys():
            if field in IGNORE:
                continue
            if field not in filterable_fields:
                raise ValidationError("Unknown filter field: '%s' (choices are %s)" % (field, ', '.join(filterable_fields)))
            if len(request.GET.getlist(field)) > 1:
                raise ValidationError("Filter field '%s' specified more than once" % field)
            queryset = self._apply_filter(queryset, field, request.GET[field])
        return queryset

    def _get_filterable_fields(self, view):
        serializer = view.get_serializer()
        return [
            field.source or field_name
            for field_name, field in serializer.fields.items()
            if not getattr(field, 'write_only', False) and not field.source == '*'
        ]

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
            kwargs[field] = value
        elif op == 'lt':
            kwargs[field + '__lt'] = value
        elif op == 'le':
            kwargs[field + '__lte'] = value
        elif op == 'gt':
            kwargs[field + '__gt'] = value
        elif op == 'ge':
            kwargs[field + '__gte'] = value
        elif op == 'ne':
            kwargs[field] = value
            revert = True
        elif op == 'in':
            vals = _parse_array(value)
            if not vals:
                raise ValidationError(field + ': IN filter expects at least one value')
            kwargs[field + '__in'] = vals
        elif op == 'out':
            vals = _parse_array(value)
            if not vals:
                raise ValidationError(field + ': OUT filter expects at least one value')
            kwargs[field + '__in'] = vals
            revert = True
        elif op == 'like':
            kwargs[field + '__icontains'] = value
        elif op == 'between':
            vals = _parse_array(value)
            if len(vals) != 2:
                raise ValidationError(field + ': BETWEEN filter expects exactly 2 values')
            kwargs[field + '__range'] = [min(vals), max(vals)]
        else:
            raise ValidationError(field + ': unknown operator "{}"'.format(op))
        # Apply the filter to the queryset
        try:
            return queryset.exclude(**kwargs) if revert else queryset.filter(**kwargs)
        except (ValueError, DjangoValidationError):
            raise ValidationError(field + ': the given operator or value are inappropriate for this field')


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
