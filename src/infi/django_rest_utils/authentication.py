from __future__ import absolute_import
from builtins import str

from django.conf import settings
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from rest_framework import authentication, exceptions

from .models import APIToken


class APITokenAuthentication(authentication.BaseAuthentication):
    '''
    Authenticates API requests by looking for a valid API token in the X-API-Token header
    The REST API token is openly displayed in the browser.
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
        return render_to_string('django_rest_utils/api_token_authentication_openly_displayed.html', dict(token=str(token)))


class APITokenAuthentication_TokenSentByEmail(APITokenAuthentication):
    '''
    Authenticates API requests by looking for a valid API token in the X-API-Token header
    The REST API token isn't displayed in the browser, but rather sent to the user by email.
    '''

    def get_authenticator_description(self, view, html):
        from django.core.urlresolvers import reverse
        token_req_url = reverse('get_rest_api_token_for_user')  # settings.REST_API_TOKEN_EMAIL_REQUEST_URL
        user_name = view.request.user.username
        return render_to_string('django_rest_utils/api_token_authentication_sent_by_email.html', dict(token_req_url=token_req_url, user_name=str(user_name)))
