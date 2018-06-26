from django.template.loader import render_to_string

from rest_framework.renderers import JSONRenderer, BaseRenderer
from rest_framework.exceptions import ValidationError
from infi.django_rest_utils.pluck import pluck_result
from itertools import chain


def _build_response(metadata, result=None, error=None):
    return dict(metadata=metadata, result=result, error=error)


def _pluck_response(response, renderer_context):
    '''
    :response: the objects to be JSON-encoded
    '''
    try:
        request = renderer_context['request']
        # if there are empty fields -> return response with default fields
        if 'fields' in request.query_params and not request.query_params.get('fields'):
            return _build_response(metadata=response['metadata'],
                                   result=response['result'])
        return _build_response(metadata=response['metadata'],
                               result=pluck_result(response['result'], request.query_params.getlist('fields')))
    except Exception as e:
        renderer_context['response'].status_code = 400
        return _build_response(metadata=dict(ready=True), error=dict(message=e.message))


def _replace_nested_with_ids(data):
    return {key: value.get('id') if isinstance(value, dict) else value for key, value in data.items()
       if not isinstance(value, list)}


def _render_to_json_obj(self, data, accepted_media_type, renderer_context):
    metadata = dict(ready=True)
    status = renderer_context['response'].status_code
    if status > 399 and 'detail' in data:
        # Error with details
        data = _build_response(metadata=metadata, error=dict(message=data['detail']))
    elif status == 400:
        # Bad request
        error = dict(message='Bad request', details=data)
        data = _build_response(metadata=metadata, error=error)
    elif data and 'page' in data:
        # Paginated results
        metadata.update(data)
        data = _pluck_response(_build_response(metadata=metadata, result=metadata.pop('results')), renderer_context)
    else:
        # Non-paginated results
        data = _pluck_response(_build_response(metadata=metadata, result=data), renderer_context)
    return data


class InfinidatJSONRenderer(JSONRenderer):

    def render(self, data, accepted_media_type=None, renderer_context=None):
        data = _render_to_json_obj(self, data, accepted_media_type, renderer_context)
        return super(InfinidatJSONRenderer, self).render(data, accepted_media_type, renderer_context)

    def get_renderer_description(self, view, html):
        if not html:
            return None
        current_plucking = view.request.GET.get("fields", "")
        context = dict(
            renderer=self,
            fields=view.get_serializer().fields.keys(),
            current_plucking=current_plucking.split(",") if current_plucking else [],
            url=view.request.build_absolute_uri(view.request.path)
        )
        return render_to_string('django_rest_utils/infinidat_json_renderer.html', context)


class FlatJSONRenderer(JSONRenderer):
    format = 'flatjson'
    def render(self, data, accepted_media_type=None, renderer_context=None):
        data = _render_to_json_obj(self, data, accepted_media_type, renderer_context)
        if data['result']:
            if isinstance(data['result'], list):
                data['result'] = [_replace_nested_with_ids(entry) for entry in data['result']]
            else:
                data['result'] = _replace_nested_with_ids(data['result'])
        return super(FlatJSONRenderer, self).render(data, accepted_media_type, renderer_context)


class DummyCSVRenderer(BaseRenderer):
    # A class only for gracefull degradation of the case where one sends format=csv without stream=1 (too late to stream
    # if arrived here and pagination makes no sense)
    format = 'csv'
    media_type = 'text/csv'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        status = renderer_context['response'].status_code
        if status > 399:
            return ''.join(data)
        else:
            raise ValueError('Setting format to csv is not supported on views that do not inherit StreamMixin')

