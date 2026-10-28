import csv
import io
import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from ..models import Holiday
from ..serializers import HolidayCreateSerializer, HolidaySerializer

logger = logging.getLogger(__name__)

_IMPORT_MAX_ROWS  = 500
_IMPORT_MAX_BYTES = 5 * 1024 * 1024


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


# ─── Holiday Calendar — Bulk Import (CSV) ─────────────────────────────────────

_IMPORT_HEADERS = ['Holiday Name', 'Date', 'Holiday Type', 'Optional', 'Company Code', 'Description']


def _can_manage_holidays(user) -> bool:
    return _has_perm(user, 'settings.edit') or _has_perm(user, 'leave.approve')


def _parse_holiday_csv_rows(file_obj) -> tuple:
    try:
        text = file_obj.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for row in reader:
            normalized = {(k or '').strip().lower(): (v or '').strip() for k, v in row.items()}
            if all(v == '' for v in normalized.values()):
                continue
            rows.append(normalized)
        return rows, None
    except Exception as exc:
        return [], f'Could not parse CSV file: {exc}'


class HolidayBulkImportView(APIView):
    """
    POST /api/leave/holidays/bulk-import/

    HR uploads a CSV of a year's holiday list per branch. This endpoint only
    imports rows the business actually supplies — it never invents dates
    itself; see HolidayBulkImportSampleView for the blank template.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser]

    def post(self, request):
        if not _can_manage_holidays(request.user):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return error('No file uploaded. Please attach a CSV file.',
                         http_status=status.HTTP_400_BAD_REQUEST)
        if uploaded_file.size > _IMPORT_MAX_BYTES:
            return error('File too large. Maximum allowed size is 5 MB.',
                         http_status=status.HTTP_400_BAD_REQUEST)
        if not (uploaded_file.name or '').lower().endswith('.csv'):
            return error('Unsupported file format. Please upload a CSV file.',
                         http_status=status.HTTP_400_BAD_REQUEST)

        rows, parse_error = _parse_holiday_csv_rows(uploaded_file)
        if parse_error:
            return error(parse_error, http_status=status.HTTP_400_BAD_REQUEST)
        if not rows:
            return error('The file contains no data rows.', http_status=status.HTTP_400_BAD_REQUEST)
        if len(rows) > _IMPORT_MAX_ROWS:
            return error(
                f'File contains {len(rows)} rows. Maximum allowed per import is {_IMPORT_MAX_ROWS}.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.branch.models import Branch
        branch_map = {}
        for b in Branch.objects.only('branch_name', 'branch_code'):
            branch_map[b.branch_name.strip().lower()] = b
            if b.branch_code:
                branch_map[b.branch_code.strip().lower()] = b

        created_count = 0
        skipped_rows  = []
        row_errors    = []

        for idx, row in enumerate(rows, start=2):
            name_raw   = row.get('holiday name') or row.get('name') or ''
            date_raw   = row.get('date') or ''
            type_raw   = (row.get('holiday type') or row.get('type') or 'national').strip().lower()
            opt_raw    = (row.get('optional') or '').strip().lower()
            branch_raw = (row.get('company code') or row.get('branch') or '').strip()
            desc_raw   = row.get('description') or ''

            branch_obj = None
            if branch_raw:
                branch_obj = branch_map.get(branch_raw.lower())
                if branch_obj is None:
                    row_errors.append({'row': idx, 'field': 'branch',
                                        'message': f'Company Code "{branch_raw}" not found.'})
                    continue

            payload = {
                'name':         name_raw,
                'date':         date_raw,
                'holiday_type': type_raw if type_raw in ('national', 'regional', 'company') else 'national',
                'is_optional':  opt_raw in ('true', 'yes', '1'),
                'description':  desc_raw,
                'branch':       branch_obj.id if branch_obj else None,
            }
            serializer = HolidayCreateSerializer(data=payload)
            if not serializer.is_valid():
                for field, msgs in serializer.errors.items():
                    msg = msgs[0] if isinstance(msgs, list) else str(msgs)
                    if 'already exists' in msg:
                        skipped_rows.append({'row': idx, 'identifier': name_raw, 'reason': msg})
                        break
                else:
                    row_errors.append({'row': idx, 'field': field, 'message': msg})
                continue

            holiday = serializer.save()
            created_count += 1
            logger.info('Holiday "%s" on %s imported by %s', holiday.name, holiday.date, request.user.email)

        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user       = request.user,
            action     = 'holiday_bulk_import',
            module     = 'hrms',
            changes    = {'total_rows': len(rows), 'created': created_count,
                          'skipped': len(skipped_rows), 'failed': len(row_errors)},
            ip_address = get_client_ip(request),
        )

        return success('Holiday import completed.', data={
            'total_rows':   len(rows),
            'created':      created_count,
            'skipped':      len(skipped_rows),
            'failed':       len(row_errors),
            'skipped_rows': skipped_rows,
            'errors':       row_errors,
        })


class HolidayBulkImportSampleView(APIView):
    """
    GET /api/leave/holidays/bulk-import/sample/

    Ships a blank CSV template with headers only — no invented holiday
    dates. HR fills in the actual business-supplied dates per branch.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _can_manage_holidays(request.user):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        from core.file_utils import build_sample_csv
        content = build_sample_csv(_IMPORT_HEADERS, [])
        response = HttpResponse(content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="holiday_import_template.csv"'
        return response
