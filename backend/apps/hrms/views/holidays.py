import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from ..models import Holiday
from ..serializers import HolidayCreateSerializer, HolidaySerializer

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    # settings.edit is this codebase's universal "sees/does everything"
    # signal — checking it here (permission-based) instead of a hardcoded
    # role name means any role actually granted settings.edit gets the same
    # bypass, and revoking it from system_admin would actually revoke it.
    return user.role.role_permissions.filter(
        permission__codename__in={codename, 'settings.edit'}
    ).exists()


def _is_unrestricted(user) -> bool:
    """
    Returns True for users who can see holidays across every branch.

    Delegates to _has_perm('settings.edit') which already grants access to
    system_admin roles and Django superusers — mirrors _is_unrestricted() in
    apps/attendance/views/hr_attendance.py.
    """
    return _has_perm(user, 'settings.edit')


class HolidayListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year     = request.query_params.get('year')
        month    = request.query_params.get('month')
        htype    = request.query_params.get('type')       # national | regional | company
        optional = request.query_params.get('optional')  # "true" → is_optional=True tab
        branch   = request.query_params.get('branch')

        if year:
            try:
                year_int = int(year)
            except (TypeError, ValueError):
                return error('Invalid year parameter.')
            from core.cache_service import HolidayCacheService
            holidays = HolidayCacheService.get_list_for_year(year_int)
            if month:
                try:
                    month_int = int(month)
                except (TypeError, ValueError):
                    return error('Invalid month parameter.')
                holidays = [h for h in holidays if h.date.month == month_int]
        else:
            qs = Holiday.objects.select_related('branch').all()
            if month:
                try:
                    qs = qs.filter(date__month=int(month))
                except (TypeError, ValueError):
                    return error('Invalid month parameter.')
            holidays = list(qs)

        if htype:
            holidays = [h for h in holidays if h.holiday_type == htype]

        if optional and optional.lower() == 'true':
            holidays = [h for h in holidays if h.is_optional]

        if branch:
            holidays = [h for h in holidays if h.branch_id is None or h.branch.branch_name == branch]
        elif not _is_unrestricted(request.user):
            user_branch = (getattr(request.user, 'branch', '') or '').strip()
            if user_branch:
                holidays = [h for h in holidays if h.branch_id is None or h.branch.branch_name == user_branch]
            else:
                holidays = [h for h in holidays if h.branch_id is None]
        # else: unrestricted user (system_admin / superuser) with no branch
        # filter requested — see every branch's holidays plus company-wide ones.

        serialized = HolidaySerializer(holidays, many=True).data
        return success('Holidays retrieved.', {
            'holidays': serialized,
            'total':    len(serialized),
        })

    def post(self, request):
        if not (_has_perm(request.user, 'settings.edit') or _has_perm(request.user, 'leave.approve')):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = HolidayCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        holiday = serializer.save()
        logger.info('Holiday "%s" on %s created by %s', holiday.name, holiday.date, request.user.email)
        return success('Holiday created.', HolidaySerializer(holiday).data, http_status=status.HTTP_201_CREATED)


class HolidayDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_holiday(self, holiday_id: str):
        try:
            return Holiday.objects.get(id=holiday_id), None
        except Holiday.DoesNotExist:
            return None, error('Holiday not found.', http_status=status.HTTP_404_NOT_FOUND)

    def get(self, request, holiday_id: str):
        holiday, err = self._get_holiday(holiday_id)
        if err:
            return err
        return success('Holiday retrieved.', HolidaySerializer(holiday).data)

    def put(self, request, holiday_id: str):
        if not (_has_perm(request.user, 'settings.edit') or _has_perm(request.user, 'leave.approve')):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        holiday, err = self._get_holiday(holiday_id)
        if err:
            return err
        serializer = HolidayCreateSerializer(holiday, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        logger.info('Holiday %s updated by %s', holiday_id, request.user.email)
        return success('Holiday updated.', HolidaySerializer(holiday).data)

    def patch(self, request, holiday_id: str):
        return self.put(request, holiday_id)

    def delete(self, request, holiday_id: str):
        if not (_has_perm(request.user, 'settings.edit') or _has_perm(request.user, 'leave.approve')):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        holiday, err = self._get_holiday(holiday_id)
        if err:
            return err
        logger.info('Holiday "%s" on %s deleted by %s', holiday.name, holiday.date, request.user.email)
        holiday.delete()
        return success('Holiday deleted.')
