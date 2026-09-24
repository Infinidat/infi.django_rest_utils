import importlib

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework import exceptions

try:
    from unittest import mock
except ImportError:
    import mock

from rest_framework.test import APIRequestFactory, force_authenticate

from infi.django_rest_utils.authentication import APITokenAuthentication
from infi.django_rest_utils.models import (APIToken, APITokenAuditLog, generate_token_secret, hash_token)
from infi.django_rest_utils import views
from infi.django_rest_utils.views import user_token_view, get_rest_api_token_for_user

User = get_user_model()


class TokenGenerationTest(TestCase):

    def test_secret_is_long_and_random(self):
        first = generate_token_secret()
        second = generate_token_secret()
        self.assertNotEqual(first, second)
        self.assertGreaterEqual(len(first), 32)

    def test_hash_is_stable_sha256_hex(self):
        self.assertEqual(hash_token('abc'), hash_token('abc'))
        self.assertEqual(len(hash_token('abc')), 64)


class APITokenManagerTest(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='alice')

    def test_create_for_user_stores_hash_not_plaintext(self):
        token = APIToken.objects.create_for_user(self.user)
        secret = token.get_plaintext()
        self.assertIsNotNone(secret)
        self.assertEqual(token.token_hash, hash_token(secret))
        # The plaintext is not stored on the row that a fresh read returns.
        reloaded = APIToken.objects.get(pk=token.pk)
        self.assertIsNone(reloaded.get_plaintext())

    def test_for_user_creates_then_returns_same(self):
        first = APIToken.objects.for_user(self.user)
        self.assertIsNotNone(first.get_plaintext())
        second = APIToken.objects.for_user(self.user)
        self.assertEqual(first.pk, second.pk)
        # An existing token has no available plaintext.
        self.assertIsNone(second.get_plaintext())

    def test_create_for_user_rotates_and_invalidates_old(self):
        first = APIToken.objects.create_for_user(self.user)
        old_hash = first.token_hash
        second = APIToken.objects.create_for_user(self.user)
        self.assertNotEqual(second.token_hash, old_hash)
        self.assertEqual(APIToken.objects.filter(user=self.user).count(), 1)

    def test_ttl_setting_sets_expiry(self):
        with self.settings(REST_API_TOKEN_TTL_DAYS=30):
            token = APIToken.objects.create_for_user(self.user)
        self.assertIsNotNone(token.expires_at)
        self.assertGreater(token.expires_at, timezone.now())

    def test_no_ttl_setting_means_no_expiry(self):
        token = APIToken.objects.create_for_user(self.user)
        self.assertIsNone(token.expires_at)


class APITokenAuthenticationTest(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='bob', is_active=True)
        self.token = APIToken.objects.create_for_user(self.user)
        self.secret = self.token.get_plaintext()
        self.factory = RequestFactory()
        self.auth = APITokenAuthentication()

    def _request(self, secret, path='/api/things/', method='get'):
        make = getattr(self.factory, method)
        return make(path, HTTP_X_API_TOKEN=secret)

    def test_valid_token_authenticates(self):
        user, _ = self.auth.authenticate(self._request(self.secret))
        self.assertEqual(user, self.user)

    def test_no_header_returns_none(self):
        self.assertIsNone(self.auth.authenticate(self.factory.get('/api/things/')))

    def test_invalid_token_raises_and_does_not_echo(self):
        with self.assertRaises(exceptions.AuthenticationFailed) as ctx:
            self.auth.authenticate(self._request('wrong-secret'))
        self.assertNotIn('wrong-secret', str(ctx.exception))

    def test_expired_token_is_rejected(self):
        self.token.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        self.token.save(update_fields=['expires_at'])
        with self.assertRaises(exceptions.AuthenticationFailed):
            self.auth.authenticate(self._request(self.secret))

    def test_inactive_user_returns_none(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertIsNone(self.auth.authenticate(self._request(self.secret)))

    def test_last_used_is_updated(self):
        self.assertIsNone(self.token.last_used_at)
        self.auth.authenticate(self._request(self.secret, path='/api/x/'))
        reloaded = APIToken.objects.get(pk=self.token.pk)
        self.assertIsNotNone(reloaded.last_used_at)

    def test_audit_row_is_written(self):
        self.auth.authenticate(self._request(self.secret, path='/api/audited/', method='post'))
        entry = APITokenAuditLog.objects.latest('timestamp')
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.endpoint, '/api/audited/')
        self.assertEqual(entry.method, 'POST')
        self.assertEqual(entry.token_key, self.token.token_hash)

    def test_audit_disabled_writes_no_row(self):
        with self.settings(REST_API_TOKEN_AUDIT_ENABLED=False):
            self.auth.authenticate(self._request(self.secret))
        self.assertEqual(APITokenAuditLog.objects.count(), 0)

    def test_audit_failure_does_not_break_auth(self):
        with mock.patch.object(APITokenAuditLog.objects, 'create', side_effect=RuntimeError('db down')):
            user, _ = self.auth.authenticate(self._request(self.secret))
        self.assertEqual(user, self.user)

    def test_last_used_failure_does_not_break_auth(self):
        with mock.patch.object(APIToken, 'save', side_effect=RuntimeError('db down')):
            user, _ = self.auth.authenticate(self._request(self.secret))
        self.assertEqual(user, self.user)

    def test_x_forwarded_for_used_only_when_trusted(self):
        req = self.factory.get('/api/x/', HTTP_X_API_TOKEN=self.secret,
                               HTTP_X_FORWARDED_FOR='203.0.113.9, 10.0.0.1', REMOTE_ADDR='10.0.0.1')
        with self.settings(REST_API_TOKEN_TRUST_X_FORWARDED_FOR=True):
            self.auth.authenticate(req)
        self.assertEqual(APITokenAuditLog.objects.latest('timestamp').source_ip, '203.0.113.9')

    def test_invalid_x_forwarded_for_falls_back_to_remote_addr(self):
        # The header is client-controlled. A non-IP value must not reach the insert.
        req = self.factory.get('/api/x/', HTTP_X_API_TOKEN=self.secret,
                               HTTP_X_FORWARDED_FOR='not-an-ip', REMOTE_ADDR='10.0.0.7')
        with self.settings(REST_API_TOKEN_TRUST_X_FORWARDED_FOR=True):
            self.auth.authenticate(req)
        self.assertEqual(APITokenAuditLog.objects.latest('timestamp').source_ip, '10.0.0.7')

    def test_long_method_is_truncated_to_field_length(self):
        # A method longer than the field must be truncated, not fail the insert.
        req = self.factory.generic('BASELINE-CONTROL-EXTRA', '/api/x/', HTTP_X_API_TOKEN=self.secret)
        self.auth.authenticate(req)
        entry = APITokenAuditLog.objects.latest('timestamp')
        self.assertEqual(entry.method, 'BASELINE-CONTROL')
        self.assertLessEqual(len(entry.method), 16)


class UserTokenViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create(username='carol')
        self.factory = RequestFactory()

    def test_get_is_rejected(self):
        request = self.factory.get('/token/')
        request.user = self.user
        response = user_token_view(request)
        self.assertEqual(response.status_code, 405)

    def test_post_rotates_and_returns_plaintext(self):
        request = self.factory.post('/token/')
        request.user = self.user
        response = user_token_view(request)
        self.assertEqual(response.status_code, 200)
        secret = response.content.decode('utf-8')
        self.assertTrue(secret)
        token = APIToken.objects.get(user=self.user)
        self.assertEqual(token.token_hash, hash_token(secret))


class GetRestApiTokenForUserAuthTest(TestCase):
    '''The email token endpoint must reject anonymous callers and must not let a non-staff
    caller request a token for another user.'''

    def setUp(self):
        self.factory = APIRequestFactory()
        self.owner = User.objects.create(username='owner', email='owner@x.com', is_active=True)
        self.other = User.objects.create(username='other', email='other@x.com', is_active=True)
        self.staff = User.objects.create(username='staff', email='staff@x.com', is_active=True, is_staff=True)

    def _post(self, user, user_name=None):
        data = {'user_name': user_name} if user_name is not None else {}
        request = self.factory.post('/get_token/', data)
        if user is not None:
            force_authenticate(request, user=user)
        with self.settings(REST_API_TOKEN_EMAIL_SUBJECT='s', REST_API_TOKEN_EMAIL_SENDER='a@b.c',
                           SECURITY_EMAIL='sec@b.c'):
            with mock.patch.object(views, 'send_email') as send_email:
                response = get_rest_api_token_for_user(request)
        return response, send_email

    def test_anonymous_is_rejected(self):
        response, send_email = self._post(user=None, user_name='owner')
        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(APIToken.objects.count(), 0)
        send_email.assert_not_called()

    def test_user_can_request_own_token(self):
        response, send_email = self._post(user=self.owner, user_name='owner')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(APIToken.objects.filter(user=self.owner).count(), 1)
        send_email.assert_called_once()

    def test_user_without_user_name_gets_own_token(self):
        response, send_email = self._post(user=self.owner)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(APIToken.objects.filter(user=self.owner).count(), 1)

    def test_non_staff_cannot_request_other_users_token(self):
        response, send_email = self._post(user=self.owner, user_name='other')
        self.assertEqual(response.status_code, 403)
        # No token is rotated for the other user.
        self.assertEqual(APIToken.objects.filter(user=self.other).count(), 0)
        send_email.assert_not_called()

    def test_staff_can_request_other_users_token(self):
        response, send_email = self._post(user=self.staff, user_name='other')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(APIToken.objects.filter(user=self.other).count(), 1)
        send_email.assert_called_once()


class MigrationBackfillLogicTest(TestCase):
    '''Test the data-migration backfill logic for legacy tokens.'''

    def _load_backfill(self):
        module = importlib.import_module('infi.django_rest_utils.migrations.0003_apitoken_hashing_and_audit_log')
        return module

    def test_backfill_hashes_and_expires_and_rotates_duplicates(self):
        module = self._load_backfill()

        class FakeRow(object):
            def __init__(self, token):
                self.token = token
                self.token_hash = None
                self.expires_at = None

            def save(self, update_fields=None):
                pass

        rows = [FakeRow('legacy-abc'), FakeRow('legacy-abc'), FakeRow(''), FakeRow('legacy-xyz')]

        class FakeQS(object):
            def __init__(self, items):
                self._items = items

            def all(self):
                return self

            def iterator(self):
                return iter(self._items)

        class FakeModel(object):
            objects = FakeQS(rows)

        class FakeApps(object):
            def get_model(self, app_label, model_name):
                return FakeModel

        module.hash_existing_tokens(FakeApps(), None)

        digests = [r.token_hash for r in rows]
        # Every row gets a 64-char hash and an expiry, and all hashes are unique.
        self.assertTrue(all(h and len(h) == 64 for h in digests))
        self.assertTrue(all(r.expires_at is not None for r in rows))
        self.assertEqual(len(set(digests)), len(digests))
        # A kept legacy token hashes to its plaintext.
        self.assertEqual(rows[3].token_hash, hash_token('legacy-xyz'))
