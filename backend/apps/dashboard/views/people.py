import logging
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Q
from django.db.models.functions import ExtractDay, ExtractMonth
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import HasCompletedOnboarding
from core.responses import error, success
from apps.dashboard.views.overview import _is_system_admin, _is_hr_or_admin

logger = logging.getLogger(__name__)
_DENIED = 'You do not have permission to perform this action.'

_TTL_LIFECYCLE = 60 * 60   # 1 h
_TTL_BIRTHDAYS = 6 * 3600  # 6 h


# ─── Shared Birthday Helpers ──────────────────────────────────────────────────

def _serialize_birthday(profile, days_until):
    user = profile.user
    return {
        'employee_id':   user.employee_id or '',
        'full_name':     user.full_name or user.email,
        'email':         user.email,
        'department':    user.department or '',
        'designation':   user.designation or '',
        'branch':        user.branch or '',
        'date_of_birth': profile.date_of_birth.strftime('%Y-%m-%d'),
        'days_until':    days_until,
    }


def _today_birthdays_data():
    today = timezone.localdate()
    key = f'dashboard:hr:birthdays:today:{today.isoformat()}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    from apps.accounts.models import EmployeeProfile
    profiles = (
        EmployeeProfile.objects
        .select_related('user')
        .filter(date_of_birth__isnull=False, user__is_active=True)
        .annotate(birth_month=ExtractMonth('date_of_birth'), birth_day=ExtractDay('date_of_birth'))
        .filter(birth_month=today.month, birth_day=today.day)
    )
    data = [_serialize_birthday(p, 0) for p in profiles]
    cache.set(key, data, _TTL_BIRTHDAYS)
    return data


def _upcoming_birthdays_data():
    today = timezone.localdate()
    key = f'dashboard:hr:birthdays:upcoming:{today.isoformat()}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    from apps.accounts.models import EmployeeProfile
    base_qs = (
        EmployeeProfile.objects
        .select_related('user')
        .filter(date_of_birth__isnull=False, user__is_active=True)
        .annotate(birth_month=ExtractMonth('date_of_birth'), birth_day=ExtractDay('date_of_birth'))
    )
    offset_map, upcoming_q = {}, Q()
    for offset in range(1, 31):
        future = today + timedelta(days=offset)
        upcoming_q |= Q(birth_month=future.month, birth_day=future.day)
        offset_map[(future.month, future.day)] = offset
    profiles = base_qs.filter(upcoming_q)
    data = sorted(
        [_serialize_birthday(p, offset_map[(p.birth_month, p.birth_day)]) for p in profiles],
        key=lambda x: x['days_until'],
    )
    cache.set(key, data, _TTL_BIRTHDAYS)
    return data


# ─── System Admin Employee Lifecycle ─────────────────────────────────────────

class SystemAdminEmployeeLifecycleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_system_admin(request.user):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import User

        today      = timezone.localdate()
        thirty_ago = today - timedelta(days=30)

        def _emp(u):
            return {
                'employee_id':     u.employee_id or '',
                'full_name':       u.full_name,
                'department':      u.department or '',
                'branch':          u.branch or '',
                'date_of_joining': str(u.date_of_joining) if u.date_of_joining else None,
            }

        new_joiners = [_emp(u) for u in User.objects.filter(
            is_active=True, date_of_joining__isnull=False, date_of_joining__gte=thirty_ago
        ).order_by('-date_of_joining')]

        anniversaries_qs = (
            User.objects
            .filter(is_active=True, date_of_joining__isnull=False, date_of_joining__month=today.month)
            .exclude(date_of_joining__year=today.year)
            .annotate(doj_day=ExtractDay('date_of_joining'))
            .order_by('doj_day')
        )
        anniversaries = [{**_emp(u), 'years': today.year - u.date_of_joining.year} for u in anniversaries_qs]

        return success('Employee lifecycle retrieved.', data={
            'new_joiners':        {'count': len(new_joiners),   'employees': new_joiners},
            'notice_period':      {'count': 0,                  'employees': []},
            'work_anniversaries': {'count': len(anniversaries), 'employees': anniversaries},
        })


# ─── System Admin Birthdays ───────────────────────────────────────────────────

class SystemAdminBirthdayTodayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_system_admin(request.user):
            return error(_DENIED, http_status=403)
        return success("Today's birthdays retrieved.", data=_today_birthdays_data())


class SystemAdminBirthdayUpcomingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_system_admin(request.user):
            return error(_DENIED, http_status=403)
        return success('Upcoming birthdays retrieved.', data=_upcoming_birthdays_data())


# ─── Audit Logs ───────────────────────────────────────────────────────────────

class SystemAdminAuditLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_system_admin(request.user):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import AuditLog

        qs = AuditLog.objects.select_related('user').order_by('-created_at')
        module = (request.query_params.get('module') or '').strip()
        if module:
            qs = qs.filter(module=module)

        try:
            limit  = min(100, max(1, int(request.query_params.get('limit',  20))))
            offset = max(0,          int(request.query_params.get('offset',  0)))
        except (ValueError, TypeError):
            limit, offset = 20, 0

        total = qs.count()
        return success('Audit logs retrieved.', data={
            'count':   total,
            'limit':   limit,
            'offset':  offset,
            'results': [
                {
                    'id':         log.id,
                    'user':       log.user.full_name if log.user else None,
                    'action':     log.action,
                    'module':     log.module,
                    'object_id':  log.object_id,
                    'ip_address': log.ip_address,
                    'created_at': log.created_at.isoformat(),
                }
                for log in qs[offset:offset + limit]
            ],
        })


# ─── HR Employee Lifecycle ────────────────────────────────────────────────────

class HREmployeeLifecycleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)

        cached = cache.get('dashboard:hr:lifecycle')
        if cached is not None:
            return success('Employee lifecycle retrieved.', data=cached)

        from apps.accounts.models import User

        today      = timezone.localdate()
        thirty_ago = today - timedelta(days=30)

        new_joiners = [
            {
                'employee_id':     u.employee_id or '',
                'full_name':       u.full_name,
                'department':      u.department or '',
                'designation':     u.designation or '',
                'date_of_joining': str(u.date_of_joining),
            }
            for u in User.objects
            .only('employee_id', 'full_name', 'department', 'designation', 'date_of_joining')
            .filter(is_active=True, date_of_joining__isnull=False, date_of_joining__gte=thirty_ago)
            .order_by('-date_of_joining')
        ]

        anniversaries = [
            {
                'employee_id':      u.employee_id or '',
                'full_name':        u.full_name,
                'department':       u.department or '',
                'years_completed':  today.year - u.date_of_joining.year,
                'anniversary_date': str(u.date_of_joining.replace(year=today.year)),
            }
            for u in User.objects
            .only('employee_id', 'full_name', 'department', 'date_of_joining')
            .filter(is_active=True, date_of_joining__isnull=False, date_of_joining__month=today.month)
            .exclude(date_of_joining__year=today.year)
            .annotate(doj_day=ExtractDay('date_of_joining'))
            .order_by('doj_day')
        ]

        data = {
            'new_joiners':        {'count': len(new_joiners),   'employees': new_joiners},
            'notice_period':      {'count': 0,                  'employees': []},
            'work_anniversaries': {'count': len(anniversaries), 'employees': anniversaries},
        }
        cache.set('dashboard:hr:lifecycle', data, _TTL_LIFECYCLE)
        return success('Employee lifecycle retrieved.', data=data)


# ─── HR Birthdays ─────────────────────────────────────────────────────────────

class HRBirthdayTodayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)
        return success("Today's birthdays retrieved.", data=_today_birthdays_data())


class HRBirthdayUpcomingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)
        return success('Upcoming birthdays retrieved.', data=_upcoming_birthdays_data())


# ─── Employee Dashboard — Birthday Announcement ──────────────────────────────

class EmployeeBirthdayTodayView(APIView):
    """
    GET /api/dashboard/employee/birthdays/today/

    Birthday announcement widget for the Employee Dashboard. Unlike
    HRBirthdayTodayView/SystemAdminBirthdayTodayView above (which gate on
    employees.view / HR-admin so reviewers can browse the whole company),
    this is open to any authenticated, onboarded employee — seeing who's
    having a birthday today is not sensitive HR data. Reuses the same
    cached _today_birthdays_data() helper, so there's no duplicate query
    or cache-invalidation logic to maintain.
    """
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        birthdays = [
            {**b, 'message': f"Happy Birthday, {b['full_name']}!"}
            for b in _today_birthdays_data()
        ]
        return success("Today's birthdays retrieved.", data={
            'count':     len(birthdays),
            'birthdays': birthdays,
        })


# ─── Employee Action Items ────────────────────────────────────────────────────

class EmployeeActionItemsView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        employee  = request.user
        cache_key = f'dashboard:employee:action_items:{employee.id}'
        items     = cache.get(cache_key)

        if items is None:
            items = self._compute_items(employee)
            cache.set(cache_key, items, 5 * 60)

        page_obj, paginator = paginate(items, request, default_page_size=5)
        return success(
            'Action items retrieved.',
            data=paginated_data(paginator, page_obj, list(page_obj)),
        )

    @staticmethod
    def _compute_items(employee) -> list:
        from apps.accounts.models import EmployeeProfile, EmployeeDocument
        from apps.attendance.models import AttendanceCorrection
        from apps.hrms.models import LeaveRequest, REQ_APPROVED, REQ_REJECTED

        items = []

        # 1. Profile completeness
        profile = EmployeeProfile.objects.filter(user=employee).first()
        if profile is None or not all([
            profile.date_of_birth, profile.gender, profile.current_address,
            profile.account_number, profile.ifsc_code,
            profile.emergency_name, profile.emergency_phone,
        ]):
            items.append({
                'action_type':    'profile_incomplete',
                'title':          'Complete Your Profile',
                'description':    'Some required profile fields are missing.',
                'status':         'pending',
                'navigation_url': '/dashboard/profile',
            })

        # 2. Missing required documents
        REQUIRED_DOCS = {'pan_card': 'PAN Card', 'aadhaar_card': 'Aadhaar Card'}
        uploaded      = set(
            EmployeeDocument.objects.filter(user=employee).values_list('document_type', flat=True)
        )
        for doc_type, label in REQUIRED_DOCS.items():
            if doc_type not in uploaded:
                items.append({
                    'action_type':    'missing_document',
                    'title':          f'Upload {label}',
                    'description':    f'{label} has not been uploaded yet.',
                    'status':         'pending',
                    # My Profile's own Documents section — where an employee
                    # can actually upload/replace a document. /dashboard/
                    # documents is the separate, unrelated Document Center.
                    'navigation_url': '/dashboard/profile',
                })

        # 3. Pending attendance corrections (max 5)
        corrections = (
            AttendanceCorrection.objects
            .filter(employee=employee, status=AttendanceCorrection.STATUS_PENDING)
            .values('date')
            .order_by('-date')[:5]
        )
        for c in corrections:
            items.append({
                'action_type':    'attendance_correction',
                'title':          f'Attendance Correction — {c["date"]}',
                'description':    'Your correction request is awaiting approval.',
                'status':         'pending',
                'navigation_url': '/dashboard/attendance',
            })

        # 4. Recent leave decisions (last 7 days)
        seven_days_ago = timezone.localdate() - timedelta(days=7)
        recent_leaves  = (
            LeaveRequest.objects
            .filter(
                employee=employee,
                status__in=[REQ_APPROVED, REQ_REJECTED],
                updated_at__date__gte=seven_days_ago,
            )
            .values('leave_type', 'status', 'start_date', 'end_date')
            .order_by('-updated_at')[:3]
        )
        for lr in recent_leaves:
            verb = 'Approved' if lr['status'] == REQ_APPROVED else 'Rejected'
            items.append({
                'action_type':    f'leave_{lr["status"]}',
                'title':          f'Leave {verb} — {lr["leave_type"].replace("_", " ").title()}',
                'description':    f'{lr["start_date"]} to {lr["end_date"]}',
                'status':         lr['status'],
                'navigation_url': '/dashboard/leave',
            })

        return items


# ─── Employee Recent Requests ─────────────────────────────────────────────────

class EmployeeRecentRequestsView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        from apps.attendance.models import AttendanceCorrection
        from apps.hrms.models import Expense, LeaveRequest

        employee = request.user
        # Each row is (sort_key, row_dict) — sort_key is the full-precision
        # created_at + pk so same-day requests (a common case) still get a
        # deterministic, stable order across separate page requests. Sorting
        # by the display-only `applied_date` (date, no time) ties constantly
        # and produced a different relative order on every request, which
        # shifted page boundaries between "Previous"/"Next" round-trips.
        recent = []

        for lr in LeaveRequest.objects.filter(employee=employee).order_by('-created_at', '-id'):
            recent.append(((lr.created_at, lr.id), {
                'request_type': 'leave',
                'title':        f'{lr.leave_type.replace("_", " ").title()} Leave',
                'applied_date': str(lr.created_at.date()),
                'status':       lr.status,
                'remarks':      lr.l1_remarks or lr.l2_remarks or '',
                'details': {
                    'start_date': str(lr.start_date),
                    'end_date':   str(lr.end_date),
                    'days':       float(lr.total_days),
                },
            }))

        for ex in Expense.objects.filter(employee=employee).order_by('-created_at', '-id'):
            recent.append(((ex.created_at, ex.id), {
                'request_type': 'expense',
                'title':        ex.title,
                'applied_date': str(ex.created_at.date()),
                'status':       ex.status,
                'remarks':      '',
                'details': {
                    'amount':   float(ex.amount),
                    'category': ex.category,
                },
            }))

        for ac in AttendanceCorrection.objects.filter(employee=employee).order_by('-created_at', '-id'):
            recent.append(((ac.created_at, ac.id), {
                'request_type': 'attendance_correction',
                'title':        f'Attendance Correction — {ac.date}',
                'applied_date': str(ac.created_at.date()),
                'status':       ac.status,
                'remarks':      ac.notes or '',
                'details': {
                    'date':       str(ac.date),
                    'punch_type': ac.punch_type,
                },
            }))

        recent.sort(key=lambda pair: pair[0], reverse=True)
        recent = [row for _sort_key, row in recent]

        page_obj, paginator = paginate(recent, request, default_page_size=5)
        return success(
            'Recent requests retrieved.',
            data=paginated_data(paginator, page_obj, list(page_obj)),
        )
