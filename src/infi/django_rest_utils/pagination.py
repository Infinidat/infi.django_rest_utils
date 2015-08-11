from django.template.loader import render_to_string

from rest_framework import pagination
from rest_framework.compat import OrderedDict
from rest_framework.response import Response


class InfinidatPaginationSerializer(pagination.PageNumberPagination):

    def get_paginated_response(self, data):
        paginator = self.page.paginator
        return Response(OrderedDict([
            ('number_of_objects', paginator.count),
            ('page_size', paginator.per_page),
            ('pages_total', paginator.num_pages),
            ('page', self.page.number),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

    def get_paginator_description(self, html):
        if not html:
            return None
        context = dict(
            pagination=self
        )
        return render_to_string('django_rest_utils/infinidat_pagination.html', context)
