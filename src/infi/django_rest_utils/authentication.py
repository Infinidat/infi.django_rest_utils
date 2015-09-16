from rest_framework import authentication
from rest_framework import exceptions

from models import APIToken


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
        return (api_token.user, None)
