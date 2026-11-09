"""
The candidate's onboarding link (recruitment path) and the HR contact shown in the candidate portal.

  - POST /onboarding/link/        exchange the one-time link for a limited session (no password, no account activation);
  - GET  /onboarding/hr-contact/  the name and email of the HR user dealing with the signed-in candidate.

The rules live in services_onboarding_link.py; the employee screens stay closed to this session until HR approves and the
candidate has activated their account (core.permissions.HasCompletedOnboardingStatus).
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.accounts.services_onboarding_link import LinkRefused, consume_onboarding_link
from apps.accounts.services_session import login_user_payload, set_auth_cookies
from apps.accounts.throttles import LoginRateThrottle
from apps.accounts.tokens import RoleBasedRefreshToken
from core.responses import error, get_client_ip, success


class OnboardingLinkExchangeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        token = str(request.data.get('token') or '').strip()
        if not token:
            return error('token is required.')
        try:
            user = consume_onboarding_link(token)
        except LinkRefused as exc:
            return error(exc.message, http_status=exc.http_status)
        except ValueError:
            return error('This onboarding link is invalid.', http_status=status.HTTP_404_NOT_FOUND)
        AuditLog.objects.create(user=user, action='onboarding_link_opened', module='accounts', object_id=str(user.pk),
                                ip_address=get_client_ip(request))
        resp = success('Onboarding link accepted.', data={'user': login_user_payload(user)})
        set_auth_cookies(resp, RoleBasedRefreshToken.for_user(user))
        return resp


class OnboardingHrContactView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        hr = request.user.hr
        if hr is None or not hr.is_active:
            return success('No HR contact assigned.', data={'name': '', 'email': ''})
        return success('HR contact retrieved.', data={'name': hr.full_name or hr.email, 'email': hr.email})
