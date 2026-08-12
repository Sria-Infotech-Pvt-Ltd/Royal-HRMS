import logging
from datetime import timedelta

from django.db.models import Q
from django.db.models.functions import ExtractDay, ExtractMonth
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, success

logger = logging.getLogger(__name__)

_DENIED = 'You do not have permission to perform this action.'


def _has_perm(user, codename):
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class BirthdayView(APIView):
    """
    GET /hrms/birthdays/
    Returns today's birthdays and upcoming birthdays in the next 7 days.
    Requires employees.view permission.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import EmployeeProfile

        today = timezone.localdate()

        base_qs = (
            EmployeeProfile.objects
            .select_related('user')
            .filter(
                date_of_birth__isnull=False,
                user__is_active=True,
            )
            .annotate(
                birth_month=ExtractMonth('date_of_birth'),
                birth_day=ExtractDay('date_of_birth'),
            )
        )

        # Today — same DB-level filter the Celery task uses
        today_profiles = base_qs.filter(
            birth_month=today.month,
            birth_day=today.day,
        )
        today_birthdays = [
            _serialize(profile, days_until=0, today_year=today.year)
            for profile in today_profiles
        ]

        # Upcoming — one DB query covering the next 7 days
        offset_map = {}
        upcoming_q = Q()
        for offset in range(1, 8):
            future = today + timedelta(days=offset)
            upcoming_q |= Q(birth_month=future.month, birth_day=future.day)
            offset_map[(future.month, future.day)] = offset

        upcoming_profiles = base_qs.filter(upcoming_q)
        upcoming_birthdays = sorted(
            [
                _serialize(
                    profile,
                    days_until=offset_map[(profile.birth_month, profile.birth_day)],
                    today_year=today.year,
                )
                for profile in upcoming_profiles
            ],
            key=lambda x: x['days_until'],
        )

        return success('Birthdays retrieved.', data={
            'today':    today_birthdays,
            'upcoming': upcoming_birthdays,
        })


class BirthdaySettingsView(APIView):
    """
    GET/PATCH /hrms/birthdays/settings/

    Admin configuration for the automatic birthday wishes feature: the
    master on/off switch plus the dashboard banner and notification copy
    templates. The email subject/body itself is configured separately via
    the 'birthday_wish' row on Settings -> Email Templates.
    """
    permission_classes = [IsAuthenticated]

    _FIELDS = [
        'is_enabled',
        'banner_message_template',
        'employee_notification_template',
        'team_notification_template',
        'manager_notification_template',
    ]

    def get(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import BirthdaySettings

        settings_obj = BirthdaySettings.get()
        return success('Birthday settings retrieved.', data=self._serialize(settings_obj))

    def patch(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import BirthdaySettings

        settings_obj = BirthdaySettings.get()
        updated_fields = []

        if 'is_enabled' in request.data:
            settings_obj.is_enabled = bool(request.data['is_enabled'])
            updated_fields.append('is_enabled')

        for field in self._FIELDS[1:]:
            if field in request.data:
                value = (request.data.get(field) or '').strip()
                if not value:
                    return error(f'{field} cannot be empty.', http_status=400)
                setattr(settings_obj, field, value)
                updated_fields.append(field)

        if updated_fields:
            settings_obj.updated_by = request.user
            settings_obj.save(update_fields=[*updated_fields, 'updated_by', 'updated_at'])

        return success('Birthday settings updated.', data=self._serialize(settings_obj))

    @staticmethod
    def _serialize(settings_obj):
        return {
            'is_enabled':                      settings_obj.is_enabled,
            'banner_message_template':         settings_obj.banner_message_template,
            'employee_notification_template':  settings_obj.employee_notification_template,
            'team_notification_template':      settings_obj.team_notification_template,
            'manager_notification_template':   settings_obj.manager_notification_template,
            'updated_at':                      settings_obj.updated_at.isoformat(),
        }


def _serialize(profile, days_until, today_year):
    user = profile.user
    return {
        'employee_id':   user.employee_id or '',
        'name':          user.full_name or user.email,
        'email':         user.email,
        'department':    user.department or '',
        'designation':   user.designation or '',
        'date_of_birth': profile.date_of_birth.strftime('%Y-%m-%d'),
        'days_until':    days_until,
        'wish_sent':     profile.birthday_wish_sent_year == today_year,
    }
