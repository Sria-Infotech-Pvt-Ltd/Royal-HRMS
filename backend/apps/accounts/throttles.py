from rest_framework.throttling import AnonRateThrottle


class CompanyScopedAnonRateThrottle(AnonRateThrottle):
    """
    Same as AnonRateThrottle, but folds the submitted company_code into the
    cache key alongside the client IP. Without this, every one of these
    endpoints throttles by IP alone — companies sharing a corporate NAT/VPN
    egress IP would rate-limit each other's logins/OTP requests, a
    functional collision between two unrelated tenants (not a data leak,
    but a real operational annoyance this project's tenancy model
    shouldn't have).
    """

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return None
        try:
            company_code = str(request.data.get('company_code', '')).strip().upper()
        except Exception:
            # Malformed body — fall back to IP-only, same as the
            # unscoped behaviour this replaces, rather than failing the
            # request over a throttle-key detail.
            company_code = ''
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{self.get_ident(request)}:{company_code}',
        }


class LoginRateThrottle(CompanyScopedAnonRateThrottle):
    scope = 'login'


class ForgotPasswordRateThrottle(CompanyScopedAnonRateThrottle):
    scope = 'forgot_password'


class OTPVerifyRateThrottle(CompanyScopedAnonRateThrottle):
    scope = 'otp_verify'
