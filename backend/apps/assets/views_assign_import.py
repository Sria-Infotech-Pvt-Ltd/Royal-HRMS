"""
Bulk asset assignment — Settings → Assets → Bulk Assign.

  POST /api/assets/assignments/import/          multipart: file (.csv/.xlsx), dry_run=true for the preview
  GET  /api/assets/assignments/import/sample/?format=csv|xlsx

Same permission (assets.edit) and employee scope as single Assign Asset;
non-admins can only assign assets of their own branch. Rows are saved
through the shared assign_asset service (see apps.assets.services_assign_import).
"""
import logging

from django.http import HttpResponse
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

from apps.accounts.models import AuditLog
from apps.assets.services_assign_import import (
    HEADERS, SAMPLE_ROWS, apply_assignments, parse_file, plan_assignments, sample_xlsx, strip_internal,
)
from apps.assets.services_import import ImportFileError
from apps.assets.views import _is_admin, _resolve_user_branch

logger = logging.getLogger(__name__)

_NO_PERMISSION = 'You do not have permission to assign assets.'


class AssetAssignImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not _has_perm(request.user, 'assets.edit'):
            return error(_NO_PERMISSION, http_status=403)
        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or Excel (.xlsx) file.')
        try:
            rows = parse_file(uploaded)
        except ImportFileError as exc:
            return error(str(exc))

        is_admin = _is_admin(request.user)
        user_branch = None if is_admin else _resolve_user_branch(request.user)
        # The confirm request re-uploads the file and is validated afresh, so
        # anything that changed since the preview is caught before saving.
        plan = plan_assignments(rows, user=request.user, is_admin=is_admin, user_branch=user_branch)

        if str(request.data.get('dry_run', '')).lower() in ('1', 'true', 'yes'):
            return success('Preview ready. Nothing has been assigned yet.', strip_internal(plan))

        result = apply_assignments(plan, user=request.user, ip_address=get_client_ip(request))
        s = result['summary']
        AuditLog.objects.create(
            user=request.user, action='asset_bulk_assign', module='assets', object_id='',
            changes={'file': uploaded.name[:200], **s},
            branch=getattr(user_branch, 'branch_name', '') or '', ip_address=get_client_ip(request),
        )
        logger.info('Asset bulk assignment by %s: %s', request.user.email, s)
        return success(
            f"Assignment finished: {s['assigned']} assigned, {s['already_assigned']} already assigned, "
            f"{s['failed']} failed.",
            result,
        )


class AssetAssignImportSampleView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= picks csv/xlsx, not a DRF renderer (same as the other sample downloads).
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    def get(self, request):
        from core.file_utils import _CSV_MIME, _XLSX_MIME, build_sample_csv

        if not _has_perm(request.user, 'assets.edit'):
            return error(_NO_PERMISSION, http_status=403)
        if (request.query_params.get('format') or 'csv').lower().strip() == 'xlsx':
            content, filename, mime = sample_xlsx(), 'asset_assignment_sample.xlsx', _XLSX_MIME
        else:
            content, filename, mime = build_sample_csv(HEADERS, SAMPLE_ROWS), 'asset_assignment_sample.csv', _CSV_MIME
        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
