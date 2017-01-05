from django.template.loader import render_to_string

from rest_framework.renderers import JSONRenderer
from infi.django_rest_utils.pluck import pluck_result, collect_items_from_string_lists
from itertools import chain


def _pluck_response(response, renderer_context):
    '''
    :response: the objects to be JSON-encoded
    '''
    try:
        request = renderer_context['request']
        return dict(metadata=response['metadata'], result=pluck_result(response['result'],
                                                                       request.query_params.getlist('fields')))
    except Exception as e:
        renderer_context['response'].status_code = 400
        return dict(metadata=dict(ready=True), result=None, error=dict(message=e.message))


def _value_to_id_str(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get('id'))
    elif isinstance(value, list):
        return ','.join([_value_to_id_str(child) for child in value])
    else:
        return str(value)


def _replace_nested_with_ids(data):
    return {key: value.get('id') if isinstance(value, dict) else value for key, value in data.items()
       if not isinstance(value, list)}



class InfinidatJSONRenderer(JSONRenderer):

    def render(self, data, accepted_media_type=None, renderer_context=None):
        metadata = dict(ready=True)
        status = renderer_context['response'].status_code
        if status > 399 and 'detail' in data:
            # Error with details
            data = dict(metadata=metadata, result=None, error=dict(message=data['detail']))
        elif status == 400:
            # Bad request
            error = dict(message='Bad request', details=data)
            data = dict(metadata=metadata, result=None, error=error)
        elif data and 'page' in data:
            # Paginated results
            metadata.update(data)
            data = _pluck_response(dict(metadata=metadata, result=metadata.pop('results')), renderer_context)
        else:
            # Non-paginated results
            data = _pluck_response(dict(metadata=metadata, result=data), renderer_context)
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
        metadata = dict(ready=True)
        status = renderer_context['response'].status_code
        if status > 399 and 'detail' in data:
            # Error with details
            data = dict(metadata=metadata, result=None, error=dict(message=data['detail']))
        elif status == 400:
            # Bad request
            error = dict(message='Bad request', details=data)
            data = dict(metadata=metadata, result=None, error=error)
        elif data and 'page' in data:
            # Paginated results
            metadata.update(data)
            falttened = [_replace_nested_with_ids(x) for x in metadata.pop('results')]
            data = _pluck_response(dict(metadata=metadata, result=falttened), renderer_context)
        else:
            # Non-paginated results
            falttened = [_replace_nested_with_ids(x) for x in data]
            data = _pluck_response(dict(metadata=metadata, result=falttened), renderer_context)
        return super(FlatJSONRenderer, self).render(data, accepted_media_type, renderer_context)

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
