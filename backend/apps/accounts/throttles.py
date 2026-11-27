from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'


class ForgotPasswordRateThrottle(AnonRateThrottle):
    scope = 'forgot_password'


class ResetPasswordRateThrottle(AnonRateThrottle):
    scope = 'reset_password'


class OTPVerifyRateThrottle(AnonRateThrottle):
    scope = 'otp_verify'


class ResendInviteRateThrottle(UserRateThrottle):
    """Keyed by the admin resending, not IP — ResendInviteView is
    authenticated, so AnonRateThrottle (IP-keyed) would be the wrong base:
    it would let one admin's resends count against every other admin
    sharing an office network, and barely limit a single admin at all."""
    scope = 'resend_invite'
