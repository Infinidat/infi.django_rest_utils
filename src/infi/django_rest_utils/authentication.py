from __future__ import absolute_import
from builtins import str
from django.template.loader import render_to_string
from rest_framework import authentication
from rest_framework import exceptions

from .models import APIToken


class APITokenAuthentication(authentication.BaseAuthentication):
    '''
    Authenticates API requests by looking for a valid API token in the X-API-Token header
    '''

    def authenticate(self, request):
        token = request.META.get('HTTP_X_API_TOKEN')
        if not token:
            return None
        try:
            api_token = APIToken.objects.get(token=token)
        except APIToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API token '%s'" % token)
        if api_token.user.is_active:
            # returns token only if the user is active
            return (api_token.user, None)
        return None

    def get_authenticator_description(self, view, html):
        token = APIToken.objects.for_user(view.request.user)
        return render_to_string('django_rest_utils/api_token_authentication.html', dict(token=str(token)))
