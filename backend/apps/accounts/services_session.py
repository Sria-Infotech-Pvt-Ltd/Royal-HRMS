"""
What a signed-in session looks like: the user payload the frontend stores, and the two httpOnly token cookies.

One place for it, used by the password login and by the candidate's one-time onboarding link, so the two can never disagree
about what a session carries or how its cookies are set (httpOnly, SameSite=Lax, Secure outside DEBUG).
"""
from __future__ import annotations

from django.conf import settings

from core.access import can_manage_branch, can_manage_team
from core.permissions import effective_permission_codenames

ACCESS_COOKIE_MAX_AGE = 900          # 15 minutes
REFRESH_COOKIE_MAX_AGE = 604800      # 7 days


def login_user_payload(user) -> dict:
    """The `user` object a successful login (or link exchange) returns."""
    from apps.accounts.views.shared import _login_assessment_status

    permissions = effective_permission_codenames(user)
    return {
        'id':                  str(user.id),
        'email':               user.email,
        'full_name':           user.full_name,
        'employee_id':         user.employee_id,
        'department':          user.department,
        'designation':         user.designation,
        'branch':              user.branch,
        'must_change_password': user.must_change_password,
        'onboarding_status':   user.onboarding_status,
        'requires_self_service_onboarding': user.requires_self_service_onboarding,
        'assessment_status':   _login_assessment_status(user),
        'permissions':         permissions,
        'can_manage_team':     can_manage_team(user),
        'can_manage_branch':   can_manage_branch(user),
        'is_superuser':        user.is_superuser or 'settings.edit' in permissions,
    }


def set_auth_cookies(response, refresh) -> None:
    secure = not settings.DEBUG
    response.set_cookie('royal_access_token', str(refresh.access_token), max_age=ACCESS_COOKIE_MAX_AGE,
                        httponly=True, secure=secure, samesite='Lax', domain=None)
    response.set_cookie('royal_refresh_token', str(refresh), max_age=REFRESH_COOKIE_MAX_AGE,
                        httponly=True, secure=secure, samesite='Lax', domain=None)
