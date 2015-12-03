from django.template.loader import render_to_string

from rest_framework.renderers import JSONRenderer
from itertools import chain


def _extract_items_from_string_lists(lists, delimiter=','):
    '''
    A fancy way to flatten a list of comma seperated lists into one list of strings
    '''
    return set(reduce(chain, (s.split(',') for s in lists)))


def _pluck_result(result, request):
    if isinstance(result, list):
        return [_pluck_result(x, request) for x in result]

    if not isinstance(result, dict):
        return result

    field_lists = request.query_params.getlist('fields')
    if len(field_lists) == 0:
        return result

    fields_to_keep = _extract_items_from_string_lists(field_lists)
    illegal_fields = fields_to_keep - set(result.keys())

    if len(illegal_fields) > 0:
        raise Exception('No such fields: %s' % ', '.join(list(illegal_fields)))

    return {k: v for (k, v) in result.iteritems() if k in fields_to_keep}


def _pluck_response(response, renderer_context):
    '''
    :response: the objects to be JSON-encoded
    '''
    try:
        return dict(metadata=response['metadata'], result=_pluck_result(response['result'], renderer_context['request']))
    except Exception as e:
        renderer_context['response'].status_code = 400
        return dict(metadata=dict(ready=True), result=None, error=dict(message=e.message))


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

    def get_renderer_description(self, html):
        if not html:
            return None
        context = dict(
            renderer=self
        )
        return render_to_string('django_rest_utils/infinidat_json_renderer.html', context)
