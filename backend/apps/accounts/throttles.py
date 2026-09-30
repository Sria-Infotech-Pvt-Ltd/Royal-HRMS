from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'


class ExternalAPIKeyThrottle(SimpleRateThrottle):
    """
    Keyed by the caller's own API key (request.auth, set by
    ExternalAPIKeyAuthentication), not by IP — an AnonRateThrottle would
    lump every external system in together under whatever anon bucket
    their shared IP happens to hit, and would also mix them in with real
    anonymous traffic (forgot-password attempts, etc.) hitting from the
    same address.
    """
    scope = 'external_api'

    def get_cache_key(self, request, view):
        api_key = getattr(request, 'auth', None)
        if api_key is None:
            return None  # unauthenticated request — let authentication itself reject it
        return self.cache_format % {'scope': self.scope, 'ident': str(api_key.pk)}


class ForgotPasswordRateThrottle(AnonRateThrottle):
    scope = 'forgot_password'


class ResetPasswordRateThrottle(AnonRateThrottle):
    scope = 'reset_password'


class OTPVerifyRateThrottle(AnonRateThrottle):
    scope = 'otp_verify'
