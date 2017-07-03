from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse
import json

from infi.django_rest_utils.pluck import pluck_result


class ViewDescriptionMixin(object):

    def get_view_description(self, html=False):
        """
        Return some descriptive text for the view, as used in OPTIONS responses
        and in the browsable API.
        """
        parts = ['<section class="docs">']
        parts += self._get_view_description_parts(html)
        parts.append('</section>')
        return mark_safe('\n'.join([part for part in parts if part]))

    def _get_view_description_parts(self, html):

        func = self.settings.VIEW_DESCRIPTION_FUNCTION
        parts = [func(self.__class__, html)]

        for authenticator in self.get_authenticators():
            if hasattr(authenticator, 'get_authenticator_description'):
                desc = authenticator.get_authenticator_description(self, html)
                parts.append(desc)

        for renderer in self.get_renderers():
            if hasattr(renderer, 'get_renderer_description'):
                desc = renderer.get_renderer_description(self, html)
                parts.append(desc)

        for cls in getattr(self, 'filter_backends', []):
            if hasattr(cls, 'get_filter_description'):
                desc = cls().get_filter_description(self, html)
                parts.append(desc)

        if self.paginator and hasattr(self.paginator, 'get_paginator_description'):
            desc = self.paginator.get_paginator_description(self, html)
            parts.append(desc)

        if isinstance(self, StreamingMixin):
            parts.append(render_to_string('django_rest_utils/infinidat_streaming.html', {}))

        return parts



class QueryTimeLimitMixin(object):

    time_limit = 30000
    timeout_message = 'Database query took to long and was cancelled.'

    def list(self, request, *args, **kwargs):
        from django.db import connections
        from django.db.utils import OperationalError
        from rest_framework.exceptions import ValidationError
        db = self.get_queryset().db
        with connections[db].cursor() as cursor:
            try:
                cursor.execute('SET statement_timeout = %s', [self.time_limit])
                return super(QueryTimeLimitMixin, self).list(request, *args, **kwargs)
            except OperationalError, e:
                if 'statement timeout' in e.message:
                    raise ValidationError(self.timeout_message)
                raise
            finally:
                cursor.execute('SET statement_timeout = DEFAULT')



class StreamingMixin(object):
    '''
    A mixin for streaming objects as a JSON array, without pagination.
    This prevents the need to serialize the whole reponse (which might be
    very large) into memory.
    To activate streaming, the request query parameters must include
    "stream=1" or "stream=true"
    '''

    def list(self, request, *args, **kwargs):
        if request.GET.get('stream', '').lower() not in ('1', 'true'):
            return super(StreamingMixin, self).list(request, *args, **kwargs)
        else:
            return StreamingHttpResponse(self._stream(request), content_type='application/json')

    def _stream(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset)
        field_list = request.query_params.getlist('fields')
        yield '{"error": null,\n"result": ['
        first = True
        for obj in queryset.iterator():
            yield '\n' if first else ',\n'
            yield json.dumps(pluck_result(serializer.to_representation(obj), field_list))
            first = False
        yield '\n], "metadata": {"ready": true}}'


@login_required
def user_token_view(request):
    """
    Returns an API token for the logged-in user.
    """
    from models import APIToken
    token = APIToken.objects.for_user(request.user)
    return HttpResponse(str(token), content_type='text/plain')
