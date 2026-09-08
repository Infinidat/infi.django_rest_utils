Overview
========
This project adds utility classes which enhance the django-rest-framework project (http://www.django-rest-framework.org/).

This project was tested under Python 2.7 and 3.5.

Usage
=====
a. Add infi.django_rest_utils to the `INSTALLED_APPS` in your settings file:

```python
    INSTALLED_APPS = (
        ...
        'rest_framework',
        'infi.django_rest_utils'
    )
```

b. Run database migrations.

c. Use the utility classes in the `REST_FRAMEWORK` settings dictionary:

```python
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'infi.django_rest_utils.renderers.InfinidatJSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'infi.django_rest_utils.filters.SimpleFilter',
        'infi.django_rest_utils.filters.InfinidatFilter',
        'infi.django_rest_utils.filters.OrderingFilter',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'infi.django_rest_utils.authentication.APITokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'ORDERING_PARAM': 'sort',
    'DEFAULT_PAGINATION_CLASS': 'infi.django_rest_utils.pagination.InfinidatPaginationSerializer',
    'PAGE_SIZE': 50,
    'PAGINATE_BY_PARAM': 'page_size',
    'MAX_PAGINATE_BY': 1000,
}
```

See below for the various classes and features provided by this library. Note that you don't have to use all of them - pick the ones that are relevant to your project.

Renderers
=========
### InfinidatJSONRenderer
Extends the default `JSONRenderer` to format the output in the style favored by INFINIDAT.
The response always contains a JSON object with 3 fields:

* **result** - the response data itself, or null in case of error.
* **metadata** - additional information about the response, for example pagination parameters.
* **error** - null in case of success, otherwise information about the error.

Also allows plucking (selecting) specific fields of every result (e.g timestamp or parsed_data.system_info.host_count).
Field plucked can be tested against non-plucked json api responses from a file by using the 'rest_utils'
``` python
bin/rest_utils pluck api_response.json timestamp system_serial parsed_data.system_info
```
To use this renderer, add `infi.django_rest_utils.renderers.InfinidatJSONRenderer` to the `DEFAULT_RENDERER_CLASSES`
list in the settings and remove `rest_framework.renderers.JSONRenderer`.

Filters
=======
### InfinidatFilter
Implements queryset filtering, with support for several comparison operators: `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `in`,
`out`, `like`, and  `between`.
For example:

    http://example.com/api/employees/?username=jj
    http://example.com/api/employees/?salary=gt:25000
    http://example.com/api/employees/?name=like:Alex&title=in:[Developer,Tester]
    http://example.com/api/employees/?hired=between:[2015-01-01,2015-01-31]

To determine which fields are available for filtering, the class checks whether the serializer implements a
`get_filterable_fields` method. This method should return a list of `FilterableField` instances.
In case the serializer does not provide such a method, the filterable fields are deduced automatically from the serializer fields.

To use this filter, add `infi.django_rest_utils.filters.InfinidatFilter` to the `DEFAULT_FILTER_BACKENDS` list in the settings.

### SimpleFilter

This type of filter uses the same `FilterableField` definitions that `InfinidatFilter` uses, but searches all string and integer fields for a match (exact match in case of integers, and substring match in case of strings). For example if the search term is *yellow sun*, the filter will return all objects that have both *yellow* and *sun* in any of their filterable fields. If the search term is quoted (*"yellow sun"*), it will be searched without splitting it into words.

The search term should appear in the URL in a query parameter named `q`. It can be used in conjuction with `InfinidatFilter` or separately.

### OrderingFilter
A subclass of the default `OrderingFilter` which supports advanced ordering. This is done by checking if the serializer
has a `get_ordering_fields` method, which is expected to return a list of `OrderingField` instances. An `OrderingField`
can be used to encapsulate ordering by more than one model field, for example:

```python
    OrderingField('name', source=('last_name', 'first_name'))
```

It can also define ordering by related fields (requires Django 1.8 or later):

```python
    OrderingField('department', source='department__name')
```

Unlike the default `OrderingFilter`, this implementation does not ignore invalid field names. Trying to sort the results
using an unidentified field name results in an error response.

To use this filter, add `infi.django_rest_utils.filters.OrderingFilter` to the `DEFAULT_FILTER_BACKENDS` list in the
settings and remove `rest_framework.filters.OrderingFilter`.

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


### InfinidatLargeSetPaginationSerializer
Extends the `InfinidatPaginationSerializer` class to return estimated object count for large datasets where counting has a performance penalty.

* **number_of_objects** - total number of items in the list
* **limited_number_of_objects** - true if the object count is limited (meaning there are more pages)
* **approximated_number_of_objects** - true if the object count is approximated
* **pages_total** - total number of pages
* **page_size** - number of items in each page
* **page** - current page number
* **next** - URL of the next page, or null if this is the last page
* **previous** - URL of the previous page, or null if this is the first page

To use, set `DEFAULT_PAGINATION_CLASS` to `infi.django_rest_utils.pagination.InfinidatLargeSetPaginationSerializer` in your settings file.


Views
=====
### ViewDescriptionMixin
This class can be used to enhance the browsable API with dynamic auto-generated documentation. The documentation is composed from:

* The view's docstring
* Information about authentication, taken from authentication classes that implement `get_authenticator_description(self, view, html)`
* Information about supported output formats, taken from renderers that implement `get_renderer_description(self, view, html)`
* Information about filtering and ordering, taken from filters that implement `get_filter_description(self, view, html)`
* Information about pagination, when the pagination class implements `get_paginator_description(self, view, html)`

All relevant classes provided by infi.django_rest_utils implement these methods, meaning that detailed documentation is automatically generated when they are used with views that extend `ViewDescriptionMixin`.

To use this mixin, add it as the **first** parent class of your views and viewsets. For example:

```python
from rest_framework import viewsets
from infi.django_rest_utils.views import ViewDescriptionMixin

class EmployeeViewSet(ViewDescriptionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ...
    queryset = ...
```

### QueryTimeLimitMixin
This mixin limits the time each database query is allowed to run (when generating a list of objects).
In case of a timeout, HTTP 400 is returned along with an error message which can be specified by
the view class.

Note: only PostgreSQL is supported.

```python
from rest_framework import viewsets
from infi.django_rest_utils.views import QueryTimeLimitMixin

class BigDataViewSet(QueryTimeLimitMixin, viewsets.ReadOnlyModelViewSet):
    time_limit = 15 * 1000 # milliseconds
    timeout_message = 'Database query took too long and was cancelled. Try limiting the query time range.'
    serializer_class = ...
    queryset = ...
```

### StreamingMixin
A view mixin that enables streaming of object lists. This is more efficient than pagination because the server does not generate the whole response before sending it to the client, so memory consumption remains low even when the response is very large.

To get a streaming response instead of a paginated response, the client needs to add `stream=true` to the URL query parameters.

To use this mixin, add it as the **first** parent class of your views and viewsets. For example:

```python
from rest_framework import viewsets
from infi.django_rest_utils.views import StreamingMixin, ViewDescriptionMixin

class EmployeeViewSet(StreamingMixin, ViewDescriptionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ...
    queryset = ...
```

Authentication
==============
### APITokenAuthentication

A simple authentication scheme where each user gets a random API token. The user must present this token in API requests via the `X-API-Token` header.
The database stores only a SHA-256 hash of the token. The token is shown once, right after it is created. The token cannot be read back later.
The api app page, /api/rest/, shows the token only right after it is created. On later visits the page states that the token is stored as a hash.

To create a new token for the logged-in user and show it once, expose `user_token_view` in your `urls.py` file. Each call to this view rotates the token. The previous token stops working.
```python
from infi.django_rest_utils.views import user_token_view

urlpatterns = [
    url(r'^user_token/$', user_token_view, name='user_token'),
]
```

### APITokenAuthentication_TokenSentByEmail

A simple authentication scheme where each user gets a random API token. The user must present this token in API requests via the `X-API-Token` header.
The api app page, /api/rest/, does not show the token. Instead, that page offers the user a link. The link posts a request that emails the token to the user.
Each email request rotates the token and emails the new value. A stored token cannot be read back, because the database stores only its hash.
The email recorded in the users database table is used for this purpose.

In order to use this authenticator class, the following changes must be made in relation with what is done when APITokenAuthentication is used:

a. Run database migrations.

b. In the settings dictionary: 

```
REST_FRAMEWORK = {
    ...
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'infi.django_rest_utils.authentication.APITokenAuthentication_TokenSentByEmail',
        ...

REST_API_TOKEN_EMAIL_SUBJECT = '...'
REST_API_TOKEN_EMAIL_SENDER = '...'
SECURITY_EMAIL = '...'
```
      
First, to get the API token assigned to the logged-in user, you can expose `user_token_view` in your `urls.py` file:
```python
from infi.django_rest_utils.views import user_token_view

urlpatterns = [
    ...
    url(r'^user_token/$', user_token_view, name='user_token'),
]
```

In addition, you must add api_token view to enable sending token with email. So your final urls.py will contain something like this:

```python
urlpatterns = [
    ...
    url(r'^user_token/$', user_token_view, name='user_token'),
    url(r'^rest/api_token/', include('infi.django_rest_utils.urls')),
]
```

### Token storage and lifecycle

The database stores only a SHA-256 hash of the token. A reader of the database cannot use the stored value.
Each token has a creation time and an optional expiry time. Authentication rejects a token after its expiry time.
By default a new token never expires. To set an expiry on new tokens, set `REST_API_TOKEN_TTL_DAYS`.

### Audit log

Each request that authenticates with a token creates one `APITokenAuditLog` row. The row records the endpoint, the method, the source IP, the user, the token hash, and the time.
The audit log is viewable in the Django admin.
The source IP is `REMOTE_ADDR` by default. To read the client IP from the first `X-Forwarded-For` hop, set `REST_API_TOKEN_TRUST_X_FORWARDED_FOR = True`. Trust `X-Forwarded-For` only behind a trusted proxy.
To delete old audit rows, run the management command:
```
django-admin prune_api_token_audit_log --days 90
```
Set `REST_API_TOKEN_AUDIT_RETENTION_DAYS` to provide a default for `--days`.

### Settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `REST_API_TOKEN_TTL_DAYS` | `None` | Days until a new token expires. `None` means no expiry. |
| `REST_API_TOKEN_AUDIT_ENABLED` | `True` | Write an audit row for each token-authenticated request. |
| `REST_API_TOKEN_AUDIT_RETENTION_DAYS` | `None` | Default age for the prune command. |
| `REST_API_TOKEN_LAST_USED_THROTTLE_SECONDS` | `0` | Minimum seconds between last-used writes. `0` writes on every request. |
| `REST_API_TOKEN_TRUST_X_FORWARDED_FOR` | `False` | Read the client IP from `X-Forwarded-For`. |

### Upgrade note

Run database migrations after you upgrade. Migration `0003` hashes each token in place, so existing tokens keep working.
Existing tokens are short and weak. The migration sets an expiry 180 days ahead on each existing token. Users must rotate to a new token before that date.
After the upgrade, the token is shown only right after it is created or rotated.

**Note**: if you are using CORS headers to allow cross-domain access to your API, be sure to include `X-API-Token` in
the `Access-Control-Allow-Headers` header, otherwise it will not be passed to your server. For example for
the *django-cors-headers* library, add this to your settings:
```python
CORS_ALLOW_HEADERS = (
    'X-API-Token',
)
```


Routers
=======
### DefaultRouter

This is a subclass of `rest_framework.routers.DefaultRouter` that provides a richer API root view. The view includes information about authentication as well as a table of contents. Additionally, a name and a description can be provided for the root view:
```python
from infi.django_rest_utils.routers import DefaultRouter

router = DefaultRouter(name='Sample API', description='This is a sample API.')
router.register(...)
```


Developing and Packaging
========================
After cloning the repository, run the following commands:

    easy_install -U infi.projector
    projector devenv build --use-isolated-python

Run `projector` to see list of available commands.


Running Tests
-------------
    bin/nosetests
    
