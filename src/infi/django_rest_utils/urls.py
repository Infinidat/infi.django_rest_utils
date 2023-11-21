try:
    # For django < 4
    from django.conf.urls import url
except ImportError:
    # For django >= 4
    from django.urls import re_path as url

from . import views


urlpatterns = [
    url(r'^get_rest_api_token_for_user/$', views.get_rest_api_token_for_user, name='get_rest_api_token_for_user'),
]
