from django.template.loader import render_to_string

from rest_framework.renderers import JSONRenderer


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
            result = metadata.pop('results')
            data = dict(metadata=metadata, result=result, error=None)
        else:
            # Non-paginated results
            data = dict(metadata=metadata, result=data, error=None)
        return super(InfinidatJSONRenderer, self).render(data, accepted_media_type, renderer_context)

    def get_renderer_description(self, html):
        if not html:
            return None
        context = dict(
            renderer=self
        )
        return render_to_string('django_rest_utils/infinidat_json_renderer.html', context)
