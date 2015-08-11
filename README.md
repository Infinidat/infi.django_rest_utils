Overview
========
This project adds utility classes which enhance the django-rest-framework project (http://www.django-rest-framework.org/).


Usage
=====
Add infi.django_rest_utils to the `INSTALLED_APPS` in your settings file:

```python
    INSTALLED_APPS = (
        ...
        'rest_framework',
        'infi.django_rest_utils'
    )
```

Use the utility classes in the `REST_FRAMEWORK` settings dictionary:

```python
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'infi.django_rest_utils.renderers.InfinidatJSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'infi.django_rest_utils.filters.InfinidatFilter',
        'infi.django_rest_utils.filters.OrderingFilter',
    ),
    'ORDERING_PARAM': 'sort',
    'DEFAULT_PAGINATION_CLASS': 'infi.django_rest_utils.pagination.InfinidatPaginationSerializer',
    'PAGE_SIZE': 50,
    'PAGINATE_BY_PARAM': 'page_size',
    'MAX_PAGINATE_BY': 1000,
}
```

See below for the various classes and features provided by this library.

Renderers
=========
### InfinidatJSONRenderer
Extends the default `JSONRenderer` to format the output in the style favored by INFINIDAT.
The response always contains a JSON object with 3 fields:

* **result** - the response data itself, or null in case of error.
* **metadata** - additional information about the response, for example pagination parameters.
* **error** - null in case of success, otherwise information about the error.

To use this renderer, add `infi.django_rest_utils.renderers.InfinidatJSONRenderer` to the `DEFAULT_RENDERER_CLASSES` list in the settings and remove `rest_framework.renderers.JSONRenderer`.

Filters
=======
### InfinidatFilter
Implements queryset filtering, with support for several comparison operators: `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `in`, `out`, `like`, and  `between`.
For example:

    http://example.com/api/employees/?username=jj
    http://example.com/api/employees/?salary=gt:25000
    http://example.com/api/employees/?name=like:Alex&title=in:[Developer,Tester]
    http://example.com/api/employees/?hired=between:[2015-01-01,2015-01-31]

The fields available for filtering are deduced automatically from the serializer in use, which is assumed to be a subclass of `rest_framework.serializers.ModelSerializer`.

To use this filter, add `infi.django_rest_utils.filters.InfinidatFilter` to the `DEFAULT_FILTER_BACKENDS` list in the settings.

### OrderingFilter
A subclass of the default `OrderingFilter` which only adds a section to the auto-generated view documentation (see Views for more information).

To use this filter, add `infi.django_rest_utils.filters.OrderingFilter` to the `DEFAULT_FILTER_BACKENDS` list in the settings and remove `rest_framework.filters.OrderingFilter`.

Pagination
==========
### InfinidatPaginationSerializer
Extends the `PageNumberPagination` class to include more information in the response metadata:

* **number_of_objects** - total number of items in the list
* **pages_total** - total number of pages
* **page_size** - number of items in each page
* **page** - current page number
* **next** - URL of the next page, or null if this is the last page
* **previous** - URL of the previous page, or null if this is the first page

To use, set `DEFAULT_PAGINATION_CLASS` to `infi.django_rest_utils.pagination.InfinidatPaginationSerializer` in your settings file.

Views
=====
### ViewDescriptionMixin
This class can be used to enhance the browsable API with dynamic auto-generated documentation. The documentation is composed from:

* The view's docstring
* Information about supported output formats, taken from renderers that implement `get_renderer_description(self, html)`
* Information about filtering and ordering, taken from filters that implement `get_filter_description(self, view, html)`
* Information about pagination, when the pagination class implements `get_paginator_description(self, html)`

All renderers, filters and paginators provided by infi.django_rest_utils implement these methods.

To use this mixin, add it as the **first** parent class of your views and viewsets. For example:

```python
from rest_framework import viewsets
from infi.django_rest_utils.views import ViewDescriptionMixin

class EmployeeViewSet(ViewDescriptionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ...
    queryset = ...
```

Developing and Packaging
========================
After cloning the repository, run the following commands:

    easy_install -U infi.projector
    projector devenv build --use-isolated-python

Run `projector` to see list of available commands.