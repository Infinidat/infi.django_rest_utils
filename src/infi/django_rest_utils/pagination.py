from django.template.loader import render_to_string
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger, Page, InvalidPage
from rest_framework import pagination
from collections import OrderedDict
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from django.conf import settings
from django.db import connections


class LargeQuerySetPage(Page):
    def has_next(self):
        if self.paginator.limited_number_of_objects:
            return self.paginator.next_page_exists(self.number)
        else:
            return super(LargeQuerySetPage, self).has_next()

class LargeQuerySetPaginator(Paginator):
    def __init__(self, *args, **kwargs):
        super(LargeQuerySetPaginator, self).__init__(*args, **kwargs)
        self.approximated_number_of_objects = False
        self.limited_number_of_objects = False

    def _get_approximate_count_for_all_objects(self):
        sql = '''
            SELECT reltuples FROM pg_class WHERE relname = '%s';
            '''
        cursor = connections[self.object_list.db].cursor()
        cursor.execute(sql % self.object_list.query.model._meta.db_table)
        result = int(cursor.fetchone()[0])
        if result:
            self.approximated_number_of_objects = True
            return result
        return self.object_list.count()

    def _get_limited_count(self):
        # Postgres is not good at counting, so we're limiting the count
        limited_list = self.object_list.order_by()[:getattr(settings, 'QUERY_OBJECT_COUNT_LIMIT', 100)]
        result = limited_list.count()
        if result >= settings.QUERY_OBJECT_COUNT_LIMIT:
            # there are too many, thus returned count is limited
            self.limited_number_of_objects = True
        return result

    def _get_count(self):
        if self._count is None:
            if self.object_list.query.where:
                self._count = self._get_limited_count()
            else:
                # https://wiki.postgresql.org/wiki/Slow_Counting
                # specifically, we can give an approximate count for all the rows in the table, or,
                # in other words, how many events we have in the store
                self._count = self._get_approximate_count_for_all_objects()
        return self._count

    def validate_number(self, number):
        "Validates the given 1-based page number."
        try:
            number = int(number)
        except ValueError:
            raise PageNotAnInteger('That page number is not an integer')
        if number < 1:
            raise EmptyPage('That page number is less than 1')
        if number > self.num_pages:
            if number == 1:
                pass
            elif self.limited_number_of_objects:
                bottom = (number - 1) * self.per_page
                top = bottom + self.per_page
                if not self.object_list[bottom:top].count():
                    raise EmptyPage('That page contains no results')
            else:
                raise EmptyPage('That page contains no results')
        return number

    def next_page_exists(self, number):
        try:
            self.page(number+1)
        except EmptyPage:
            return False
        return True

    def page(self, number):
        "Returns a Page object for the given 1-based page number."
        number = self.validate_number(number)
        bottom = (number - 1) * self.per_page
        top = bottom + self.per_page
        if top + self.orphans >= self.count and not self.limited_number_of_objects:
            top = self.count
        return LargeQuerySetPage(self.object_list[bottom:top], number, self)

    count = property(_get_count)


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

    # Has to be set since django rest utils since commit 3806af3d15dcbf9c5e1e390d1ae3808f12191342 on django rest
    # framework: https://github.com/tomchristie/django-rest-framework/commit/3806af3d15dcbf9c5e1e390d1ae3808f12191342
    page_size_query_param = 'page_size'

    def get_paginator_description(self, view, html):
        if not html:
            return None
        context = dict(
            pagination=self,
            url=view.request.build_absolute_uri(view.request.path)
        )
        return render_to_string('django_rest_utils/infinidat_pagination.html', context)


class InfinidatLargeSetPaginationSerializer(InfinidatPaginationSerializer):
    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate a queryset if required, either returning a
        page object, or `None` if pagination is not configured for this view.
        """

        page_size = self.get_page_size(request)
        if not page_size:
            return None

        paginator = LargeQuerySetPaginator(queryset, page_size)
        page_number = request.query_params.get(self.page_query_param, 1)
        if page_number in self.last_page_strings:
            page_number = paginator.num_pages

        try:
            self.page = paginator.page(page_number)
        except InvalidPage as exc:
            msg = self.invalid_page_message.format(
                page_number=page_number, message=exc.message
            )
            raise NotFound(msg)

        if paginator.num_pages > 1 and self.template is not None:
            # The browsable API should display pagination controls.
            self.display_page_controls = True

        self.request = request
        return list(self.page)

    def get_paginated_response(self, data):
        paginator = self.page.paginator
        return Response(OrderedDict([
            ('number_of_objects', max(self.page.paginator.count, (self.page.number-1)*self.page.paginator.per_page + len(data))),
            ('limited_number_of_objects', self.page.paginator.limited_number_of_objects),
            ('approximated_number_of_objects', self.page.paginator.approximated_number_of_objects),
            ('page_size', paginator.per_page),
            ('pages_total', max(self.page.paginator.num_pages, self.page.number + (1 if self.page.paginator.next_page_exists(self.page.number) else 0))),
            ('page', self.page.number),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

    def get_paginator_description(self, view, html):
        if not html:
            return None
        context = dict(
            pagination=self,
            url=view.request.build_absolute_uri(view.request.path)
        )
        return render_to_string('django_rest_utils/infinidat_large_queryset_pagination.html', context)
