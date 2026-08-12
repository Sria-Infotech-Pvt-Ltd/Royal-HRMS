"""
Shared birthday-hierarchy helpers.

Centralizes "who are this person's teammates / who is their manager"
so apps.hrms.tasks.send_birthday_wishes (notification fan-out) and the
dashboard's MyBirthdayWidgetsView (personal/team/manager cards) query the
same relationships the same way.
"""
from __future__ import annotations

from django.db.models.functions import ExtractDay, ExtractMonth


def get_peers(user):
    """Active users who share `user`'s reporting manager, excluding `user`.

    Empty queryset if `user` has no reporting manager — there is no "team"
    to compare against in that case.
    """
    from apps.accounts.models import User

    if not user.reporting_manager_id:
        return User.objects.none()
    return (
        User.objects
        .filter(reporting_manager_id=user.reporting_manager_id, is_active=True)
        .exclude(id=user.id)
    )


def serialize_birthday_person(user, profile=None) -> dict:
    profile = profile or getattr(user, 'profile', None)
    return {
        'employee_id':   user.employee_id or '',
        'full_name':     user.full_name or user.email,
        'email':         user.email,
        'department':    user.department or '',
        'designation':   user.designation or '',
        'date_of_birth': (
            profile.date_of_birth.strftime('%Y-%m-%d')
            if profile and profile.date_of_birth else None
        ),
    }


def get_team_birthdays_today(user, today) -> list[dict]:
    from apps.accounts.models import EmployeeProfile

    peer_ids = list(get_peers(user).values_list('id', flat=True))
    if not peer_ids:
        return []

    profiles = (
        EmployeeProfile.objects
        .select_related('user')
        .filter(user_id__in=peer_ids, date_of_birth__isnull=False)
        .annotate(birth_month=ExtractMonth('date_of_birth'), birth_day=ExtractDay('date_of_birth'))
        .filter(birth_month=today.month, birth_day=today.day)
    )
    return [serialize_birthday_person(p.user, p) for p in profiles]


def get_manager_birthday_today(user, today) -> dict | None:
    from apps.accounts.models import EmployeeProfile

    if not user.reporting_manager_id:
        return None

    profile = (
        EmployeeProfile.objects
        .select_related('user')
        .filter(user_id=user.reporting_manager_id, date_of_birth__isnull=False)
        .annotate(birth_month=ExtractMonth('date_of_birth'), birth_day=ExtractDay('date_of_birth'))
        .filter(birth_month=today.month, birth_day=today.day)
        .first()
    )
    if not profile:
        return None
    return serialize_birthday_person(profile.user, profile)
