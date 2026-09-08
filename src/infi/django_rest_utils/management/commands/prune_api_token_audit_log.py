from __future__ import absolute_import

import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import APITokenAuditLog


def prune_audit_log(days, batch_size=5000):
    '''Delete audit rows older than the given number of days. Return the count deleted.

    Delete in batches to avoid a long lock on a large table.
    '''
    cutoff = timezone.now() - datetime.timedelta(days=days)
    total_deleted = 0
    while True:
        ids = list(APITokenAuditLog.objects.filter(timestamp__lt=cutoff).values_list('id', flat=True)[:batch_size])
        if not ids:
            break
        deleted, _ = APITokenAuditLog.objects.filter(id__in=ids).delete()
        total_deleted += deleted
    return total_deleted


class Command(BaseCommand):
    help = 'Delete API token audit log rows older than the retention period.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=None,
                            help='Delete rows older than this many days. Falls back to REST_API_TOKEN_AUDIT_RETENTION_DAYS.')
        parser.add_argument('--batch-size', type=int, default=5000,
                            help='Number of rows to delete per batch.')

    def handle(self, *args, **options):
        days = options['days']
        if days is None:
            days = getattr(settings, 'REST_API_TOKEN_AUDIT_RETENTION_DAYS', None)
        if not days:
            self.stderr.write('Set --days or REST_API_TOKEN_AUDIT_RETENTION_DAYS.')
            return
        deleted = prune_audit_log(days, options['batch_size'])
        self.stdout.write('Deleted %d API token audit log rows older than %d days.' % (deleted, days))
