from django.db import models
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string


class APITokenManager(models.Manager):

    def for_user(self, user):
        try:
            return self.get(user=user)
        except APIToken.DoesNotExist:
            return self.create(user=user, token=get_random_string())


class APIToken(models.Model):

    user = models.ForeignKey(User)
    token = models.CharField(max_length=64)

    objects = APITokenManager()

    class Meta:
        verbose_name = 'API token'

    def __unicode__(self):
        return self.token

