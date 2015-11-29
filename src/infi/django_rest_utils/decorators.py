from django.http.response import HttpResponseForbidden
from django.utils.decorators import available_attrs, wraps


def ajax_login_required(function):
    """
    Decorator for views that checks that the user is logged in, resulting in a
    403 Unautherized response if not.
    """
    @wraps(function, assigned=available_attrs(function))
    def wrapped_function(request, *args, **kwargs):
        if request.user.is_authenticated():
            return function(request, *args, **kwargs)
        else:
            return HttpResponseForbidden()
    return wrapped_function
