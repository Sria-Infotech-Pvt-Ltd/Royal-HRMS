import csv
import io
import logging
import secrets
import smtplib
import string
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from core.date_utils import format_date_display
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from apps.accounts.models import AuditLog, Company, User
from apps.accounts.utils import send_template_email
from core.pagination import paginate, paginated_data
from core.template_context import candidate_context, candidate_interview_location, company_name, universal_context
from ..models import Candidate, CandidateEmail, CandidateLog, ReferralBonus, ReferralRule
from ..serializers import (
    CandidateBulkImportRowSerializer,
    CandidateCreateSerializer,
    CandidateDetailSerializer,
    CandidateEmailSerializer,
    CandidateListSerializer,
    CandidateUpdateSerializer,
    ReferralBonusSerializer,
    ReferralRuleSerializer,
    ReferralSubmitSerializer,
)

logger = logging.getLogger(__name__)

from apps.recruitment.views.shared import *  # noqa: F401,F403



# ── Bulk Candidate Import ─────────────────────────────────────────────────────
# (_IMPORT_COL_MAP lives in shared.py — used by _normalize_import_headers there.)

_MAX_IMPORT_ROWS = 1000
_MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 MB










class CandidateBulkImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser]

    def post(self, request):
        if not _has_perm(request.user, 'recruitment.create'):
            return error(
                'Only HR and System Admin users can import candidates.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        upload = request.FILES.get('file')
        if not upload:
            return error(
                'No file provided. Send file= as multipart/form-data.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        if upload.size > _MAX_IMPORT_BYTES:
            return error(
                'File exceeds the 5 MB limit. Split the file and try again.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        fname = upload.name.lower()
        if fname.endswith('.csv'):
            rows, parse_err = _parse_csv_rows(upload)
        elif fname.endswith('.xlsx') or fname.endswith('.xls'):
            rows, parse_err = _parse_xlsx_rows(upload)
        else:
            return error(
                'Unsupported file type. Upload a .csv or .xlsx file.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        if parse_err:
            return error(parse_err, http_status=status.HTTP_400_BAD_REQUEST)
        if not rows:
            return error(
                'The file contains no data rows.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        if len(rows) > _MAX_IMPORT_ROWS:
            return error(
                f'File contains {len(rows)} rows. Maximum allowed per import is '
                f'{_MAX_IMPORT_ROWS}. Split the file and upload in batches.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        # Pre-load branch lookup once for the entire batch.
        from apps.branch.models import Branch
        branch_map: dict = {}
        for b in Branch.objects.only('id', 'branch_name', 'branch_code'):
            branch_map[b.branch_name.strip().lower()] = b
            if b.branch_code:
                branch_map[b.branch_code.strip().lower()] = b

        # Pre-load existing emails + phones for DB-level duplicate detection.
        existing_emails: set = set(Candidate.objects.values_list('email', flat=True))
        existing_phones: set = set(
            Candidate.objects
            .exclude(phone='')
            .exclude(phone__isnull=True)
            .values_list('phone', flat=True)
        )

        # Track values seen in this file for intra-file duplicate detection.
        seen_emails: set = set()
        seen_phones: set = set()

        to_create:      list = []
        to_create_meta: list = []
        row_errors:     list = []
        skipped_rows:   list = []

        for i, raw in enumerate(rows, start=2):  # row 1 is the header
            row = _normalize_import_headers(raw)
            ser = CandidateBulkImportRowSerializer(data=row)

            if not ser.is_valid():
                for field, msgs in ser.errors.items():
                    row_errors.append({
                        'row':     i,
                        'field':   field,
                        'message': msgs[0] if isinstance(msgs, list) else str(msgs),
                    })
                continue

            data  = ser.validated_data
            email = data['email']
            phone = (data.get('phone') or '').strip()

            # Duplicates are skipped silently — not treated as failures.
            if email in existing_emails or email in seen_emails:
                skipped_rows.append({
                    'row':        i,
                    'identifier': email,
                    'reason':     'Already exists',
                })
                continue

            if phone and (phone in existing_phones or phone in seen_phones):
                skipped_rows.append({
                    'row':        i,
                    'identifier': email,
                    'reason':     'Phone number already exists',
                })
                continue

            branch     = None
            branch_raw = (data.get('branch_name') or '').strip()
            if branch_raw:
                branch = branch_map.get(branch_raw.lower())
                if branch is None:
                    row_errors.append({
                        'row':        i,
                        'field':      'branch',
                        'identifier': email,
                        'message':    (
                            f'Company Code "{branch_raw}" not found. '
                            'Use an existing Company Code name or code.'
                        ),
                    })
                    continue

            has_interview_date = bool(data.get('interview_date'))
            to_create.append(Candidate(
                name             = data['name'],
                email            = email,
                phone            = phone,
                position_applied = data['position_applied'],
                branch           = branch,
                interview_date   = data.get('interview_date'),
                interview_mode   = data.get('interview_mode') or '',
                notes            = data.get('notes') or '',
                # Mirrors _advance_status_on_interview_scheduled — a row that
                # already carries an interview_date must not sit at "Pending"
                # once imported, same as a candidate created one at a time.
                status           = Candidate.STATUS_INTERVIEW_SCHEDULED if has_interview_date else Candidate.STATUS_PENDING,
                added_by         = request.user,
            ))
            to_create_meta.append({'row': i, 'identifier': email})
            seen_emails.add(email)
            if phone:
                seen_phones.add(phone)

        created_count = 0
        created_rows  = []
        if to_create:
            with transaction.atomic():
                Candidate.objects.bulk_create(to_create)
                created_count = len(to_create)
                created_rows  = to_create_meta

                # bulk_create() bypasses .save(), so none of the normal
                # per-row hooks ran — fire the interview-scheduled email for
                # every imported row that already has an interview_date, same
                # as a candidate created one at a time via CandidateListCreateView.
                for candidate in to_create:
                    if candidate.interview_date:
                        _fire_interview_date_emails_if_needed(candidate, old_interview_date=None)

        total         = len(rows)
        skipped_count = len(skipped_rows)
        failed        = len(row_errors)

        AuditLog.objects.create(
            user       = request.user,
            action     = 'bulk_candidate_import',
            module     = 'recruitment',
            changes    = {
                'total_rows': total,
                'created':    created_count,
                'skipped':    skipped_count,
                'failed':     failed,
            },
            ip_address = get_client_ip(request),
        )

        logger.info(
            'Bulk import by %s: %d created, %d skipped, %d failed (total %d)',
            request.user.email, created_count, skipped_count, failed, total,
        )

        return success(
            'Bulk import completed.',
            data={
                'total_rows':   total,
                'created':      created_count,
                'skipped':      skipped_count,
                'failed':       failed,
                'created_rows': created_rows,
                'skipped_rows': skipped_rows,
                'errors':       row_errors,
            },
            http_status=status.HTTP_200_OK if failed == 0 else status.HTTP_207_MULTI_STATUS,
        )


# ─── Candidate Bulk Import — Sample Template ──────────────────────────────────

class CandidateBulkImportSampleView(APIView):
   
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= selects csv/xlsx file type, not DRF response renderer.
        # Bypass DRF's renderer filtering to prevent Http404 on unknown formats.
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    _HEADERS = [
        'Candidate Name', 'Email', 'Mobile Number', 'Position Applied',
        'Company Code', 'Interview Date', 'Interview Mode', 'Notes',
    ]
    _SAMPLE_ROWS = [
        [
            'Rahul Sharma', 'rahul.sharma@email.com', '9876543210',
            'Software Engineer', 'Mumbai HQ', '2026-07-25', 'In-Person', '',
        ],
        [
            'Priya Patel', 'priya.patel@email.com', '9123456789',
            'Product Manager', 'Delhi Branch', '2026-07-26', 'Video Call', 'Strong candidate',
        ],
    ]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(
                'You do not have permission to download the candidate import template.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        from core.file_utils import build_sample_csv, build_sample_xlsx, _CSV_MIME, _XLSX_MIME

        fmt = request.query_params.get('format', 'csv').lower().strip()
        if fmt == 'xlsx':
            content  = build_sample_xlsx(self._HEADERS, self._SAMPLE_ROWS, 'Candidate Import')
            filename = 'candidate_import_sample.xlsx'
            mime     = _XLSX_MIME
        else:
            content  = build_sample_csv(self._HEADERS, self._SAMPLE_ROWS)
            filename = 'candidate_import_sample.csv'
            mime     = _CSV_MIME

        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
