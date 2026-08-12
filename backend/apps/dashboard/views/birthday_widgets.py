from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import HasCompletedOnboarding
from core.responses import success


class MyBirthdayWidgetsView(APIView):
    """
    GET /dashboard/birthdays/mine/

    Strictly hierarchy-scoped birthday widgets for the requesting user:
      - team:    teammates (same reporting manager) with a birthday today
      - manager: the requesting user's reporting manager's birthday today, else null

    The personal "it's my birthday" banner is intentionally NOT scoped here —
    it's shown company-wide via EmployeeBirthdayTodayView (people.py) /
    EmpBirthdayAnnouncement, same audience as everyone else's birthday
    announcement. This endpoint only covers the two widgets that ARE
    restricted to the caller's own reporting hierarchy.
    """
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        from apps.accounts.models import BirthdaySettings
        from apps.hrms.birthday_utils import get_manager_birthday_today, get_team_birthdays_today

        today    = timezone.localdate()
        user     = request.user
        settings = BirthdaySettings.get()

        team = [
            {**person, 'message': settings.team_notification_template.format(employee_name=person['full_name'])}
            for person in get_team_birthdays_today(user, today)
        ]

        manager = get_manager_birthday_today(user, today)
        if manager:
            manager = {
                **manager,
                'message': settings.manager_notification_template.format(employee_name=manager['full_name']),
            }

        return success('Birthday widgets retrieved.', data={'team': team, 'manager': manager})
