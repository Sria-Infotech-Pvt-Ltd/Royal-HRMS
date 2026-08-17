from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from apps.tenants.models import PlatformAdmin


class PlatformAdminAuthentication(BaseAuthentication):
    """
    Authenticates platform-admin requests from the 'platform_access_token'
    httpOnly cookie — a completely separate cookie and claim namespace from
    apps.accounts.authentication.CookieJWTAuthentication's tenant-user
    'royal_access_token', so a platform-admin session can never be mistaken
    for (or grant) access to any company's data, and a company login can
    never reach this layer.
    """

    def authenticate(self, request):
        raw_token = request.COOKIES.get('platform_access_token')
        if not raw_token:
            return None

        try:
            token = AccessToken(raw_token)
        except TokenError:
            raise AuthenticationFailed('Invalid or expired session.')

        if not token.get('is_platform_admin'):
            return None

        try:
            admin = PlatformAdmin.objects.get(pk=token['platform_admin_id'], is_active=True)
        except PlatformAdmin.DoesNotExist:
            raise AuthenticationFailed('Account not found or inactive.')

        return (admin, token)
