from rest_framework import serializers
from infi.django_rest_utils.filters import OrderingField, FilterableField


class DefaultModelSerializer(serializers.ModelSerializer):
    def get_filterable_fields(self):
        model = self.Meta.model
        return model.get_filterable_fields() if hasattr(model, 'get_filterable_fields') else FilterableField.for_model(model)

    def get_ordering_fields(self):
        model = self.Meta.model
        return model.get_ordering_fields() if hasattr(model, 'get_ordering_fields') else OrderingField.for_model(model)
