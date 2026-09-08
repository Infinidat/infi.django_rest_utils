# -*- coding: utf-8 -*-
# Harden the API token model: store a hash instead of the plaintext token, add lifecycle
# and usage fields, and add the audit log. See INV-1395.
import datetime
import hashlib

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

# Force a rotation window on migrated legacy tokens. Legacy 12-character tokens are weak.
LEGACY_TOKEN_TTL_DAYS = 180


def hash_existing_tokens(apps, schema_editor):
    '''Backfill token_hash from the legacy plaintext token. Force expiry on legacy tokens.'''
    from django.utils import timezone
    from django.utils.crypto import get_random_string

    APIToken = apps.get_model('django_rest_utils', 'APIToken')
    expires_at = timezone.now() + datetime.timedelta(days=LEGACY_TOKEN_TTL_DAYS)
    seen_digests = set()
    for row in APIToken.objects.all().iterator():
        secret = row.token or ''
        digest = hashlib.sha256(secret.encode('utf-8')).hexdigest() if secret else None
        if not secret or digest in seen_digests:
            # Rotate an empty or duplicate legacy token to a fresh strong secret.
            secret = get_random_string(48)
            digest = hashlib.sha256(secret.encode('utf-8')).hexdigest()
        seen_digests.add(digest)
        row.token_hash = digest
        row.expires_at = expires_at
        row.save(update_fields=['token_hash', 'expires_at'])


def noop_reverse(apps, schema_editor):
    # The plaintext token cannot be recovered from the hash. A downgrade loses the tokens.
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('django_rest_utils', '0002_useractivity'),
    ]

    operations = [
        # token_hash starts as null so the add needs no one-off default on existing rows.
        migrations.AddField(
            model_name='apitoken',
            name='token_hash',
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='apitoken',
            name='note',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='apitoken',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='apitoken',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='apitoken',
            name='last_used_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='apitoken',
            name='last_used_ip',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.RunPython(hash_existing_tokens, noop_reverse),
        # Set the final not-null, unique shape after the backfill. The backfill rotates
        # empty or duplicate legacy tokens, so every token_hash is unique here.
        migrations.AlterField(
            model_name='apitoken',
            name='token_hash',
            field=models.CharField(max_length=64, unique=True),
        ),
        # Make the plaintext column nullable first so a reverse can re-add it safely.
        migrations.AlterField(
            model_name='apitoken',
            name='token',
            field=models.CharField(blank=True, default='', max_length=64, null=True),
        ),
        migrations.RemoveField(
            model_name='apitoken',
            name='token',
        ),
        migrations.CreateModel(
            name='APITokenAuditLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_key', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('endpoint', models.CharField(max_length=512)),
                ('method', models.CharField(max_length=16)),
                ('source_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('token', models.ForeignKey(blank=True, null=True,
                                            on_delete=django.db.models.deletion.SET_NULL,
                                            to='django_rest_utils.apitoken')),
                ('user', models.ForeignKey(blank=True, null=True,
                                           on_delete=django.db.models.deletion.SET_NULL,
                                           related_name='api_token_audit_logs',
                                           to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'API token audit log',
                'ordering': ('-timestamp',),
            },
        ),
    ]
