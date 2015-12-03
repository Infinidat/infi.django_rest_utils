from rest_framework import viewsets
from functools import partial

class FilteredSerializerMixin(object):
    def get_filtered_serializer(self, request, *args, **kwargs):
        serializer = super(FilteredSerializerMixin, self).get_serializer(*args, **kwargs)
        self.filter_fields_in_serializer(request, serializer)
        if hasattr(serializer, 'child'):
            self.filter_fields_in_serializer(request, serializer.child)
        return serializer

    def filter_fields_in_serializer(self, request, serializer):
        if not hasattr(serializer, 'fields'):
            return
        if 'fields' not in request.query_params:
            return
        field_names = set()
        for item in request.query_params.getlist('fields'):
            field_names.update(item.split(','))
        for field_name in serializer.fields.keys():
            if field_name not in field_names:
                serializer.fields.pop(field_name)
        return


class ReadOnlyModelViewSet(FilteredSerializerMixin, viewsets.ReadOnlyModelViewSet):
    pass


class ModelViewSet(FilteredSerializerMixin, viewsets.ModelViewSet):
    pass
