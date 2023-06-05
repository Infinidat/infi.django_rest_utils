from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^get_rest_api_token_for_user/$', views.get_rest_api_token_for_user, name='get_rest_api_token_for_user'),
]