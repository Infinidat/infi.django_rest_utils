from __future__ import absolute_import
from builtins import map
from builtins import str
from builtins import zip
from builtins import object
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse, HttpResponseBadRequest
from rest_framework.relations import ManyRelatedField, RelatedField
from rest_framework.serializers import BaseSerializer
from rest_framework.exceptions import APIException
import json
from functools import partial
from itertools import repeat, chain, islice
from infi.django_rest_utils.pluck import pluck_result, collect_items_from_string_lists
from .utils import to_csv_row, composition, wrap_with_try_except
from django.utils.encoding import escape_uri_path
import logging

logger = logging.getLogger(__name__)
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
            except OperationalError as e:
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
        is_csv = request.GET.get('format', '').lower() == 'csv'
        is_stream = request.GET.get('stream', '').lower() in ('1', 'true') or is_csv
        if is_stream:
            return self._create_streamed_response(request, is_csv)
        else:
            return super(StreamingMixin, self).list(request, *args, **kwargs)

    def _infer_field_list(self, request, serializer):
        field_list_param = request.query_params.getlist('fields')
        is_flat = request.GET.get('format', '').lower() in ('csv', 'flatjson')

        if field_list_param:
            return collect_items_from_string_lists(field_list_param)
        elif is_flat:
            field_list = []
            for name, field in serializer.get_fields().items():
                if isinstance(field, ManyRelatedField):
                    continue
                if isinstance(field, BaseSerializer):
                    field_list.append(name + '.id')
                    continue
                field_list.append(name)
            return field_list
        else:
            return None

    def _infer_filename(self):
        try:
            return self.get_view_name().replace(' ', '').lower()
        except:
            return 'api_data'

    def _infer_content_disposition(self, extension):
        return 'attachment; filename="{filename}.{extension}"'.format(filename=self._infer_filename(),
                                                                      extension=extension)

    def _create_streamed_response(self, request, is_csv):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset)
        field_list = self._infer_field_list(request, serializer)
        if is_csv:
            content_type='text/csv'
            header = ','.join(field_list) + '\n'
            footer = ''
            delimiter = ''
            dict_renderering_function = partial(to_csv_row, field_list)
            extension = 'csv'
        else:
            content_type = 'application/json'
            header = '{"error": null, "metadata": {"ready": true}, "result": [\n'
            footer = '\n]}'
            delimiter = ',\n'
            dict_renderering_function = json.dumps
            extension = 'json'

        renderering_function = composition(
            serializer.to_representation, # Model => dict
            partial(pluck_result, field_list=field_list), # pluck fields from dict
            dict_renderering_function # dict => str
        )
        safe_rendering_function = wrap_with_try_except(renderering_function,
                                                       on_except= lambda e: json.dumps({'error': e.message}),
                                                       logger=logger)
        # map every model object to its string representation
        rendered_queryset_iterator = map(safe_rendering_function, queryset.iterator())

        # Add a delimiter -before- every "row"
        # The chain and zip pattern is common for combining two iterators in a round robin fasion
        with_leading_delimiters = chain.from_iterable(zip(repeat(delimiter),
                                                           rendered_queryset_iterator))

        # Add header and footer, and chain the iterators while ensuring the first
        # member is taken without a leading delimiter
        with_header_and_footer = chain(
            repeat(header, 1), # header
            islice(rendered_queryset_iterator, 1), # first "row", no trailing delimiter
            with_leading_delimiters, # rest of the rows with a delimiter before each one
            repeat(footer, 1) # footer
        )
        response = StreamingHttpResponse(with_header_and_footer, content_type=content_type)
        response['Content-Disposition'] = self._infer_content_disposition(extension)
        return response


@login_required
def user_token_view(request):
    """
    Returns an API token for the logged-in user.
    """
    from .models import APIToken
    token = APIToken.objects.for_user(request.user)
    return HttpResponse(str(token), content_type='text/plain')
