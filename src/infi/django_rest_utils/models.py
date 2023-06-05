from builtins import object

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string


class APITokenManager(models.Manager):

    def for_user(self, user):
        try:
            return self.get(user=user)
        except APIToken.DoesNotExist:
            return self.create(user=user, token=get_random_string())


class APIToken(models.Model):

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=64)

    objects = APITokenManager()

    class Meta:
        verbose_name = 'API token'

    def __unicode__(self):
        return self.token

    def __str__(self):
        return self.token


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
            # print('cur - ', current_time, ' last - ', self.last_rest_api_token_email_sent_at, ' diff - ', time_passed_since_last_rest_api_token_email_sent.total_seconds(), ' interval - ', UserActivity.seconds_interval_between_successive_rest_api_token_emails, ' may - ', time_passed_since_last_rest_api_token_email_sent.total_seconds() >= UserActivity.seconds_interval_between_successive_rest_api_token_emails)
            return time_passed_since_last_rest_api_token_email_sent.total_seconds() >= UserActivity.seconds_interval_between_successive_rest_api_token_emails
        return True  # No REST API token email yet sent to this user, so such an email may be sent now.
