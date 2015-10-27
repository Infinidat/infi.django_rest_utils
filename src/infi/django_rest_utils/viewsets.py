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


class PluckableListViewMixin(object):
    def list(self, request, *args, **kwargs):
        self.get_serializer = partial(self.get_filtered_serializer, request)
        return super(PluckableListViewMixin, self).list(request, *args, **kwargs)


class PluckableRetrieveModelMixin(object):
    def retrieve(self, request, *args, **kwargs):
        self.get_serializer = partial(self.get_filtered_serializer, request)
        return super(PluckableRetrieveModelMixin, self).retrieve(request, *args, **kwargs)


class ReadOnlyModelViewSet(PluckableRetrieveModelMixin, PluckableListViewMixin, FilteredSerializerMixin, viewsets.ReadOnlyModelViewSet):
    pass


class ModelViewSet(PluckableRetrieveModelMixin, PluckableListViewMixin, FilteredSerializerMixin, viewsets.ModelViewSet):
    pass
