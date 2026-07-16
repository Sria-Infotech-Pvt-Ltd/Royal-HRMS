from rest_framework_simplejwt.authentication import JWTAuthentication as _JWTAuthentication


class CookieJWTAuthentication(_JWTAuthentication):
    """
    Authenticates via two sources in priority order:
    1. httpOnly cookie 'royal_access_token' — web browsers
    2. Authorization: Bearer <token> header — Flutter mobile
    """

    def authenticate(self, request):
        # 1. Cookie (web browsers — token is never readable by JS)
        raw_token = request.COOKIES.get('royal_access_token')

        # 2. Authorization header (Flutter mobile — no cookie support)
        if not raw_token:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                raw_token = auth_header[len('Bearer '):]

        if not raw_token:
            return None

        try:
            validated = self.get_validated_token(raw_token.encode())
            return self.get_user(validated), validated
        except Exception:
            return None
