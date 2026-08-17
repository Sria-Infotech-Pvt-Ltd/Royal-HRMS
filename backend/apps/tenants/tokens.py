from __future__ import annotations

from rest_framework_simplejwt.tokens import RefreshToken


class PlatformAdminRefreshToken(RefreshToken):
    """
    Deliberately does NOT use RefreshToken.for_user() — that sets the
    standard 'user_id' claim, which the tenant side of this app
    (apps.accounts) also uses to mean a tenant User's pk. Keeping
    platform-admin tokens on an entirely distinct claim name
    (platform_admin_id, not user_id) means the two token types can never be
    confused for each other even if a cookie name were ever reused by
    mistake.
    """

    @classmethod
    def for_admin(cls, admin) -> 'PlatformAdminRefreshToken':
        token = cls()
        token['platform_admin_id'] = str(admin.id)
        token['is_platform_admin'] = True
        token['email']             = admin.email
        token['full_name']         = admin.full_name
        return token
