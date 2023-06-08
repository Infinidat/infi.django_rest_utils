from django.http.response import HttpResponseForbidden
from functools import wraps, WRAPPER_ASSIGNMENTS


def ajax_login_required(function):
    """
    Decorator for views that checks that the user is logged in, resulting in a
    403 Unauthorized response if not.
    """
    @wraps(function, assigned=WRAPPER_ASSIGNMENTS)
    def wrapped_function(request, *args, **kwargs):
        if request.user.is_authenticated:
            return function(request, *args, **kwargs)
        else:
            return HttpResponseForbidden()
    return wrapped_function
