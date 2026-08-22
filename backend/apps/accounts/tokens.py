from __future__ import annotations

from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


def _volatile_claims(user) -> dict:
    """
    Claims that can change mid-session (onboarding submitted/approved,
    assessment completed, role reassigned) — factored out so both
    RoleBasedRefreshToken.for_user (login) and FreshClaimsTokenRefreshSerializer
    (every subsequent /token/refresh/) derive them the exact same way.
    frontend/proxy.ts reads these straight off the signed access token for
    its onboarding/assessment/superuser route gates — see that file's
    getOnboardingStatus/getAssessmentStatus/getCanManageTeam/getCanManageBranch/getIsSuperuser.
    """
    return {
        'onboarding_status': user.onboarding_status,
        'assessment_status': user.assessment_status,
        'can_manage_team':   bool(user.role and user.role.can_manage_team),
        'can_manage_branch': bool(user.role and user.role.can_manage_branch),
        'is_superuser':      user.is_superuser,
    }


class RoleBasedRefreshToken(RefreshToken):
    @classmethod
    def for_user(cls, user) -> RoleBasedRefreshToken:
        token = super().for_user(user)

        token['role']                 = user.role.name if user.role else None
        token['full_name']            = user.full_name
        token['email']                = user.email
        token['employee_id']          = user.employee_id or ''
        token['department']           = user.department or ''
        token['branch']               = user.branch or ''
        token['must_change_password'] = user.must_change_password
        token['permissions'] = (
            [rp.permission.codename for rp in user.role.role_permissions.all()]
            if user.role else []
        )
        for key, value in _volatile_claims(user).items():
            token[key] = value

        return token


class FreshClaimsTokenRefreshSerializer(TokenRefreshSerializer):
    """
    SimpleJWT's default refresh just copies whatever custom claims were
    already baked into the presented refresh token — with
    ROTATE_REFRESH_TOKENS=True that means onboarding_status/assessment_status/
    can_manage_team/is_superuser would otherwise stay frozen at whatever
    they were at login for the entire 7-day refresh-token lifetime, no
    matter how many times the token rotates. Since proxy.ts's route gates
    read these straight off the access token, that staleness would either
    wrongly keep bouncing an already-onboarded user back to /onboarding,
    or (going the other way) fail to promote a newly-approved/completed
    status until the user logs in again. Re-derives just these volatile
    claims from the current User row on every refresh; everything
    else (role, permissions, email, ...) is left as SimpleJWT's default
    copy-from-refresh-token behaviour, since those rarely change mid-session
    and a role/permission change already forces re-login in this app.
    """

    def validate(self, attrs):
        # Must decode the presented refresh token BEFORE calling
        # super().validate() below — with BLACKLIST_AFTER_ROTATION=True,
        # that call blacklists this exact token as a side effect, and
        # decoding it again afterward would raise (blacklisted tokens fail
        # verification), silently skipping the freshness overlay via the
        # except-and-return-data fallback below on every single refresh.
        from apps.accounts.models import User

        try:
            decoded = self.token_class(attrs['refresh'])
            user = User.objects.get(pk=decoded[api_settings.USER_ID_CLAIM])
        except Exception:
            user = None

        data = super().validate(attrs)

        if user is None:
            # Decoding/lookup failure here shouldn't fail a refresh that
            # SimpleJWT's own validation already accepted — just skip the
            # freshness overlay and return the tokens as SimpleJWT built them.
            return data

        fresh = _volatile_claims(user)

        access = AccessToken(data['access'])
        for key, value in fresh.items():
            access[key] = value
        data['access'] = str(access)

        if 'refresh' in data:
            new_refresh = self.token_class(data['refresh'])
            for key, value in fresh.items():
                new_refresh[key] = value
            data['refresh'] = str(new_refresh)

        return data
