from rest_framework import metadata
from django.utils.encoding import force_text


class SimpleMetadata(metadata.SimpleMetadata):

    def determine_actions(self, request, view):
        '''
        Adds the GET HTTP method to the methods for which an OPTIONS HTTP method request returns metadata for
        Based on the implementation of determine_actions in super class in django rest framework version 3.3.3
        '''
        actions = super(SimpleMetadata, self).determine_actions(request, view)
        actions['GET'] = self.get_serializer_info(view.get_serializer())
        return actions

    def get_field_info(self, field):
        """
        Overrides SimpleMetadata.get_field_info since the above was tweaked to prevent it from displaying related field
        choices:
        https://github.com/tomchristie/django-rest-framework/commit/014e24b02418bb10a2c6d34058aa839e4749ec55
        This patch reverts that change by copying a section of the code from the last commit before that change:

        """
        field_info = super(SimpleMetadata, self).get_field_info(field)

        if not field_info.get('read_only') and hasattr(field, 'choices'):
            field_info['choices'] = [
                {
                    'value': choice_value,
                    'display_name': force_text(choice_name, strings_only=True)
                }
                for choice_value, choice_name in field.choices.items()
            ]

        return field_info
