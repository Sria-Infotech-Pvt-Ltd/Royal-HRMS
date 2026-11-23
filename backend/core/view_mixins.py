"""
Shared view behaviour for DRF views.

RouteMatchedMethodsMixin: some views serve two URLs (a list and a detail, for example /settings/onboarding-fields/ and
/settings/onboarding-fields/<field_key>/). Their methods fit only one of the two: get() lists, patch(field_key) edits one.
Calling the other one (PATCH on the list URL, GET on the detail URL) made Python raise a TypeError, which came back to the
caller as "An unexpected error occurred" (HTTP 500) and wrote a full traceback to errors.log. The right answer is HTTP 405
"Method not allowed", which is what this mixin returns.
"""
import inspect

from rest_framework.exceptions import MethodNotAllowed


class RouteMatchedMethodsMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)   # sign-in and permission checks first, as for any view
        handler = getattr(self, request.method.lower(), None)
        if handler is None:
            return
        try:
            inspect.signature(handler).bind(request, *args, **kwargs)
        except TypeError:
            raise MethodNotAllowed(request.method)
