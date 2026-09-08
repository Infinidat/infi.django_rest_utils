from __future__ import absolute_import
from builtins import str

import logging

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import authentication, exceptions

try:
    from django.urls import reverse
except ImportError:
    # Django < 2
    from django.core.urlresolvers import reverse

from .models import APIToken, APITokenAuditLog, hash_token
from .utils import get_client_ip

logger = logging.getLogger(__name__)


class APITokenAuthentication(authentication.BaseAuthentication):
    '''
    Authenticates API requests by looking for a valid API token in the X-API-Token header
    The database stores only the hash of the token.
    '''

    def authenticate(self, request):
        token = request.META.get('HTTP_X_API_TOKEN')
        if not token:
            return None
        try:
            api_token = APIToken.objects.get(token_hash=hash_token(token))
        except APIToken.DoesNotExist:
            # Do not echo the presented token. That would leak it into logs and responses.
            raise exceptions.AuthenticationFailed('Invalid API token')
        if api_token.is_expired():
            raise exceptions.AuthenticationFailed('API token has expired')
        if not api_token.user.is_active:
            # returns token only if the user is active
            return None
        self._record_usage(request, api_token)
        return (api_token.user, None)

    def _record_usage(self, request, api_token):
        '''Record the token use. Never let telemetry break authentication.'''
        try:
            self._update_last_used(request, api_token)
        except Exception as e:
            logger.error('Failed to update API token last-used: %s', e)
        if getattr(settings, 'REST_API_TOKEN_AUDIT_ENABLED', True):
            try:
                # A failed write aborts the surrounding transaction in Postgres. Keep the
                # write in its own savepoint. A failure then rolls back only this write.
                with transaction.atomic():
                    APITokenAuditLog.objects.create(
                        token=api_token,
                        token_key=api_token.token_hash,
                        user=api_token.user,
                        endpoint=request.path[:512],
                        method=request.method[:16],
                        source_ip=get_client_ip(request),
                    )
            except Exception as e:
                logger.error('Failed to write API token audit log: %s', e)

    def _update_last_used(self, request, api_token):
        '''Update the last-used time and IP. Skip the write inside the throttle window.'''
        now = timezone.now()
        throttle_seconds = getattr(settings, 'REST_API_TOKEN_LAST_USED_THROTTLE_SECONDS', 0) or 0
        if throttle_seconds and api_token.last_used_at:
            if (now - api_token.last_used_at).total_seconds() < throttle_seconds:
                return
        api_token.last_used_at = now
        api_token.last_used_ip = get_client_ip(request)
        # Keep the write in its own savepoint. A failure then does not abort the request
        # transaction in Postgres.
        with transaction.atomic():
            api_token.save(update_fields=['last_used_at', 'last_used_ip'])

    def get_authenticator_description(self, view, html):
        api_token = APIToken.objects.for_user(view.request.user)
        # The plaintext is available only when the token was just created in this call.
        plaintext = api_token.get_plaintext()
        return render_to_string('django_rest_utils/api_token_authentication_openly_displayed.html',
                                dict(token=plaintext, expires_at=api_token.expires_at))


class APITokenAuthentication_TokenSentByEmail(APITokenAuthentication):
    '''
    Authenticates API requests by looking for a valid API token in the X-API-Token header
    The REST API token isn't displayed in the browser, but rather sent to the user by email.
    '''

    def get_authenticator_description(self, view, html):
        token_req_url = reverse('get_rest_api_token_for_user')  # settings.REST_API_TOKEN_EMAIL_REQUEST_URL
        user_name = view.request.user.username
        return render_to_string('django_rest_utils/api_token_authentication_sent_by_email.html', dict(token_req_url=token_req_url, user_name=str(user_name)))
