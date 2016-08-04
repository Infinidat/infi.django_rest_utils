from rest_framework import metadata

class SimpleMetadata(metadata.SimpleMetadata):

    def determine_actions(self, request, view):
        '''
        Adds the GET HTTP method to the methods for which an OPTIONS HTTP method request returns metadata for
        Based on the implementation of determine_actions in super class in django rest framework version 3.3.3
        '''
        actions = super(SimpleMetadata, self).determine_actions(request, view)
        actions['GET'] = self.get_serializer_info(view.get_serializer())
        return actions
