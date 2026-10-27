"""Who has how much access: every active employee with the number of permissions they hold today.

GET /settings/employee-access/  (settings.view)
  ?search=   name, email or employee id
  ?branch=   exact branch name
  ?position= a position id (people holding that seat today)
  ?access=   extra (has personal extra permissions) | superuser | no_seat
  ?page=&page_size=   (20 per page)

A person's total is the company baseline + the seat they hold today + their personal extras, counted once each.
A superuser has every permission that exists.
"""
import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import Permission, Placement, PositionPermission, User
from core.access import _covers_today, baseline_codenames, holders_of_position
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, success

logger = logging.getLogger(__name__)

ACCESS_FILTERS = ('extra', 'superuser', 'no_seat')


def _filtered_users(params):
    users = User.objects.filter(is_active=True).order_by('full_name')
    search = params.get('search', '').strip()
    if search:
        users = users.filter(Q(full_name__icontains=search) | Q(email__icontains=search) | Q(employee_id__icontains=search))
    if params.get('branch'):
        users = users.filter(branch=params['branch'])
    if params.get('position'):
        users = users.filter(pk__in=holders_of_position(params['position']).values('pk'))
    access = params.get('access', '')
    if access == 'extra':
        users = users.filter(extra_permissions__isnull=False).distinct()
    elif access == 'superuser':
        users = users.filter(is_superuser=True)
    elif access == 'no_seat':
        users = users.exclude(pk__in=Placement.objects.filter(_covers_today('')).values('employee_id'))
    return users


def _seat_details(user_ids):
    """({user id: seat title}, {user id: {codenames from that seat}}) for the seats held today."""
    titles = {
        placement.employee_id: placement.position.title
        for placement in Placement.objects.filter(_covers_today(''), employee_id__in=user_ids).select_related('position')
    }
    codenames = {}
    rows = PositionPermission.objects.filter(
        _covers_today('position__placements__'), position__placements__employee_id__in=user_ids,
    ).values_list('position__placements__employee_id', 'permission__codename')
    for user_id, codename in rows:
        codenames.setdefault(user_id, set()).add(codename)
    return titles, codenames


def _extra_codenames(user_ids):
    from apps.accounts.models import EmployeePermission

    extras = {}
    for user_id, codename in EmployeePermission.objects.filter(employee_id__in=user_ids).values_list('employee_id', 'permission__codename'):
        extras.setdefault(user_id, set()).add(codename)
    return extras


def _rows(users):
    ids = [user.pk for user in users]
    baseline = baseline_codenames()
    all_count = Permission.objects.count()
    titles, seat_codenames = _seat_details(ids)
    extras = _extra_codenames(ids)
    rows = []
    for user in users:
        seat = seat_codenames.get(user.pk, set())
        extra = extras.get(user.pk, set())
        rows.append({
            'uuid': str(user.pk),
            'employee_id': user.employee_id,
            'full_name': user.full_name,
            'branch': user.branch,
            'position': titles.get(user.pk, ''),
            'is_superuser': user.is_superuser,
            'total': all_count if user.is_superuser else len(baseline | seat | extra),
            'from_baseline': len(baseline),
            'from_seat': len(seat),
            'extra': len(extra),
        })
    return rows


class EmployeeAccessListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'settings.view'):
            return error('You do not have permission to view access settings.', http_status=status.HTTP_403_FORBIDDEN)
        access = request.query_params.get('access', '')
        if access and access not in ACCESS_FILTERS:
            return error(f'access must be one of: {", ".join(ACCESS_FILTERS)}.', http_status=status.HTTP_400_BAD_REQUEST)
        page_obj, paginator = paginate(_filtered_users(request.query_params), request)
        return success(f'{paginator.count} employee(s) found.', paginated_data(paginator, page_obj, _rows(list(page_obj))))
