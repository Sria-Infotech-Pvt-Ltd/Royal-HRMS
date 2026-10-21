"""
Bulk asset import — Settings → Assets → Bulk Import.

  POST /api/assets/import/          multipart: file (.csv/.xlsx), dry_run=true for the preview
  GET  /api/assets/import/sample/?format=csv|xlsx

Same permission (assets.create) and branch rule as single Add Asset; every
row is validated by AssetSerializer (see apps.assets.services_import).
"""
import logging

from django.http import HttpResponse
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

from apps.accounts.models import AuditLog
from apps.assets.services_import import (
    HEADERS, ImportFileError, apply_import, parse_file, plan_import, sample_rows, sample_xlsx, strip_internal,
)
from apps.assets.views import _is_admin, _resolve_user_branch

logger = logging.getLogger(__name__)


class AssetImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not _has_perm(request.user, 'assets.create'):
            return error('You do not have permission to create assets.', http_status=403)
        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or Excel (.xlsx) file.')
        try:
            rows = parse_file(uploaded)
        except ImportFileError as exc:
            return error(str(exc))

        is_admin = _is_admin(request.user)
        user_branch = None if is_admin else _resolve_user_branch(request.user)
        plan = plan_import(rows, user=request.user, is_admin=is_admin, user_branch=user_branch)

        if str(request.data.get('dry_run', '')).lower() in ('1', 'true', 'yes'):
            return success('Preview ready. Nothing has been saved yet.', strip_internal(plan))

        result = apply_import(plan, user=request.user, ip_address=get_client_ip(request))
        s = result['summary']
        AuditLog.objects.create(
            user=request.user, action='asset_bulk_import', module='assets', object_id='',
            changes={'file': uploaded.name[:200], **s},
            branch=getattr(user_branch, 'branch_name', '') or '', ip_address=get_client_ip(request),
        )
        logger.info('Asset bulk import by %s: %s', request.user.email, s)
        return success(
            f"Import finished: {s['created']} created, {s['duplicate']} duplicate, {s['failed']} failed.",
            result,
        )


class AssetImportSampleView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= picks csv/xlsx, not a DRF renderer (same as the other sample downloads).
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    def get(self, request):
        from apps.branch.models import Branch
        from core.file_utils import _CSV_MIME, _XLSX_MIME, build_sample_csv

        if not _has_perm(request.user, 'assets.create'):
            return error('You do not have permission to create assets.', http_status=403)
        branch = _resolve_user_branch(request.user) if not _is_admin(request.user) else (
            _resolve_user_branch(request.user) or Branch.objects.filter(status=Branch.STATUS_ACTIVE).order_by('branch_name').first()
        )
        rows = sample_rows(branch_code=branch.branch_code if branch else 'YOUR-BRANCH-CODE')
        if (request.query_params.get('format') or 'csv').lower().strip() == 'xlsx':
            content, filename, mime = sample_xlsx(rows), 'asset_import_sample.xlsx', _XLSX_MIME
        else:
            content, filename, mime = build_sample_csv(HEADERS, rows), 'asset_import_sample.csv', _CSV_MIME
        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
