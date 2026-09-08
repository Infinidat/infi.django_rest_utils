import hashlib

from django.conf import settings
from django.contrib.auth import get_user_model; User = get_user_model()
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

try:
    import secrets
except ImportError:  # Python < 3.6 has no secrets module.
    secrets = None


# A SHA-256 hex digest is 64 characters.
TOKEN_HASH_LENGTH = 64


def generate_token_secret():
    '''Return a new high-entropy token secret as text.'''
    if secrets is not None:
        return secrets.token_urlsafe(32)
    # Fallback for Python < 3.6. get_random_string is also CSPRNG-backed.
    return get_random_string(48)


def hash_token(secret):
    '''Return the SHA-256 hex digest of a token secret.'''
    return hashlib.sha256(secret.encode('utf-8')).hexdigest()


class APITokenManager(models.Manager):

    def _configured_ttl_days(self):
        '''Return the configured token lifetime in days, or None for no expiry.'''
        return getattr(settings, 'REST_API_TOKEN_TTL_DAYS', None)

    def create_for_user(self, user, note=''):
        '''Create a new token for the user and return it. Remove any existing token first.

        The plaintext secret is available on the returned instance as ``_plaintext``.
        The secret is shown only once. The database stores only its hash.
        '''
        # Keep one token per user. Rotation invalidates the previous token.
        self.filter(user=user).delete()
        secret = generate_token_secret()
        expires_at = None
        ttl_days = self._configured_ttl_days()
        if ttl_days:
            expires_at = timezone.now() + timezone.timedelta(days=ttl_days)
        api_token = self.create(user=user, token_hash=hash_token(secret), note=note, expires_at=expires_at)
        api_token._plaintext = secret
        return api_token

    def for_user(self, user):
        '''Return the token for the user. Create one if none exists.

        On creation the plaintext secret is set on the instance as ``_plaintext``.
        An existing token has no available plaintext, because the database stores only the hash.
        '''
        try:
            return self.get(user=user)
        except APIToken.DoesNotExist:
            return self.create_for_user(user)


class APIToken(models.Model):

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=TOKEN_HASH_LENGTH, unique=True)
    note = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)

    objects = APITokenManager()

    # Transient plaintext secret. Set only right after generation. Never stored.
    _plaintext = None

    class Meta:
        verbose_name = 'API token'

    def __str__(self):
        return 'API token for %s' % (self.user,)

    def is_expired(self):
        '''Return True if the token has an expiry time in the past.'''
        return self.expires_at is not None and self.expires_at <= timezone.now()

    def get_plaintext(self):
        '''Return the plaintext secret if it is available, else None.

        The secret is available only on the instance that generated it.
        '''
        return self._plaintext


class APITokenAuditLog(models.Model):

    # Keep the log row if the token is deleted. token_key holds the hash as a durable link.
    token = models.ForeignKey('APIToken', null=True, blank=True, on_delete=models.SET_NULL)
    token_key = models.CharField(max_length=TOKEN_HASH_LENGTH, blank=True, default='', db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='api_token_audit_logs')
    endpoint = models.CharField(max_length=512)
    method = models.CharField(max_length=16)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'API token audit log'
        ordering = ('-timestamp',)

    def __str__(self):
        return '%s %s %s' % (self.timestamp, self.method, self.endpoint)


class UserActivity(models.Model):

    seconds_interval_between_successive_rest_api_token_emails = 24 * 60 * 60  # The user may request that the token will be sent to him/her no more than once a day.

    user                                = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, db_index=False)
    last_rest_api_token_email_sent_at   = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return 'User activity for %s' % (self.user)

    def may_send_rest_api_token_email(self):
        if self.last_rest_api_token_email_sent_at:
            current_time = timezone.now()
            time_passed_since_last_rest_api_token_email_sent = current_time - self.last_rest_api_token_email_sent_at
            return time_passed_since_last_rest_api_token_email_sent.total_seconds() >= UserActivity.seconds_interval_between_successive_rest_api_token_emails
        return True  # No REST API token email yet sent to this user, so such an email may be sent now.
