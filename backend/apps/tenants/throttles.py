from rest_framework.throttling import AnonRateThrottle


class PlatformAdminLoginRateThrottle(AnonRateThrottle):
    """
    Own scope, not accounts.throttles.LoginRateThrottle's 'login' bucket —
    platform admin is the highest-privilege account in this system and
    shouldn't share a rate-limit bucket with (or be affected by) ordinary
    tenant login attempts from the same IP.
    """
    scope = 'platform_admin_login'
