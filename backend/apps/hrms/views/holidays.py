import logging

from django.db.models import Q
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
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class HolidayListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year     = request.query_params.get('year')
        month    = request.query_params.get('month')
        htype    = request.query_params.get('type')       # national | regional | company
        optional = request.query_params.get('optional')  # "true" → is_optional=True tab
        branch   = request.query_params.get('branch')

        qs = Holiday.objects.all()

        if year:
            try:
                qs = qs.filter(date__year=int(year))
            except (TypeError, ValueError):
                return error('Invalid year parameter.')

        if month:
            try:
                qs = qs.filter(date__month=int(month))
            except (TypeError, ValueError):
                return error('Invalid month parameter.')

        if htype:
            qs = qs.filter(holiday_type=htype)

        if optional and optional.lower() == 'true':
            qs = qs.filter(is_optional=True)

        if branch:
            qs = qs.filter(Q(branch__isnull=True) | Q(branch__branch_name=branch))
        else:
            user_branch = (getattr(request.user, 'branch', '') or '').strip()
            if user_branch:
                qs = qs.filter(Q(branch__isnull=True) | Q(branch__branch_name=user_branch))
            else:
                qs = qs.filter(branch__isnull=True)

        holidays = HolidaySerializer(qs, many=True).data
        return success('Holidays retrieved.', {
            'holidays': holidays,
            'total':    len(holidays),
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
