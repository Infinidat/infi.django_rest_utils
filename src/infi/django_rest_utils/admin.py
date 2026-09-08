from __future__ import absolute_import

from django.contrib import admin
from django.template.response import TemplateResponse

try:
    from django.urls import reverse
except ImportError:
    # Django < 2
    from django.core.urlresolvers import reverse

from .models import APIToken, APITokenAuditLog, generate_token_secret, hash_token


class APITokenAdmin(admin.ModelAdmin):

    list_display = ('user', 'note', 'created_at', 'expires_at', 'last_used_at', 'last_used_ip')
    list_select_related = ('user',)
    search_fields = ('user__username', 'note')
    # raw_id_fields avoids a dependency on the User admin. autocomplete_fields would need
    # search_fields on the User admin, which this shared library does not control.
    raw_id_fields = ('user',)
    readonly_fields = ('token_hash', 'created_at', 'last_used_at', 'last_used_ip')
    fields = ('user', 'note', 'expires_at', 'token_hash', 'created_at', 'last_used_at', 'last_used_ip')

    def save_model(self, request, obj, form, change):
        if not change and not obj.token_hash:
            # A new token was added in the admin. Generate a secret and keep it on the
            # instance. response_add shows it once on the page.
            secret = generate_token_secret()
            obj.token_hash = hash_token(secret)
            obj._plaintext = secret
        super(APITokenAdmin, self).save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        secret = obj.get_plaintext()
        if secret:
            # Show the secret on the page, not through messages. The message framework can
            # store the secret in the session or cache backend.
            context = dict(
                self.admin_site.each_context(request),
                title='API token created',
                token=secret,
                expires_at=obj.expires_at,
                changelist_url=reverse('admin:%s_%s_changelist' % (obj._meta.app_label, obj._meta.model_name)),
            )
            return TemplateResponse(request, 'django_rest_utils/admin/api_token_created.html', context)
        return super(APITokenAdmin, self).response_add(request, obj, post_url_continue)


class APITokenAuditLogAdmin(admin.ModelAdmin):

    list_display = ('timestamp', 'user', 'method', 'endpoint', 'source_ip')
    list_select_related = ('user',)
    list_filter = ('method', 'timestamp')
    search_fields = ('user__username', 'endpoint', 'source_ip')
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


admin.site.register(APIToken, APITokenAdmin)
admin.site.register(APITokenAuditLog, APITokenAuditLogAdmin)
