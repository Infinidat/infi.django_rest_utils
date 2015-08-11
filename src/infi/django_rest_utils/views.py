from django.utils.safestring import mark_safe


class ViewDescriptionMixin(object):

    def get_view_description(self, html=False):
        """
        Return some descriptive text for the view, as used in OPTIONS responses
        and in the browsable API.
        """
        parts = []
        func = self.settings.VIEW_DESCRIPTION_FUNCTION
        parts.append(func(self.__class__, html))

        for renderer in self.get_renderers():
            desc = renderer.get_renderer_description(html) if hasattr(renderer, 'get_renderer_description') else None
            parts.append(desc)

        for cls in getattr(self, 'filter_backends', []):
            desc = cls().get_filter_description(self, html) if hasattr(cls, 'get_filter_description') else None
            parts.append(desc)

        if self.paginator and hasattr(self.paginator, 'get_paginator_description'):
            desc = self.paginator.get_paginator_description(html)
            parts.append(desc)

        return mark_safe('\n'.join([part for part in parts if part]))
