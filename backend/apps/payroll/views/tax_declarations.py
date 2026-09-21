import logging

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success

from ..models import EmployeeTaxDeclaration
from ..serializers import EmployeeTaxDeclarationSaveSerializer, EmployeeTaxDeclarationSerializer

logger = logging.getLogger(__name__)


def _current_fy_start() -> int:
    from apps.accounts.utils import get_company_financial_year_config, get_fy_start_year
    from datetime import date
    config = get_company_financial_year_config()
    return get_fy_start_year(date.today(), config['financial_year_start_month'])


class MyTaxDeclarationView(APIView):
    """GET/PATCH /payroll/tax-declarations/me/ — the current employee's own
    declaration for the current financial year, created on first GET
    (defaults: new regime, no investments declared) rather than requiring a
    separate "create" step — there's exactly one row per employee per FY, so
    get-or-create is simpler than a real list/create split here."""
    permission_classes = [IsAuthenticated]

    def _get_or_create(self, user):
        declaration, _ = EmployeeTaxDeclaration.objects.get_or_create(
            employee=user, financial_year_start=_current_fy_start(),
        )
        return declaration

    def get(self, request):
        declaration = self._get_or_create(request.user)
        return success('Tax declaration retrieved.', EmployeeTaxDeclarationSerializer(declaration).data)

    def patch(self, request):
        declaration = self._get_or_create(request.user)
        if declaration.status == EmployeeTaxDeclaration.STATUS_APPROVED:
            return error('This declaration has already been approved and can no longer be edited.', http_status=409)
        serializer = EmployeeTaxDeclarationSaveSerializer(declaration, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        return success('Declaration saved.', EmployeeTaxDeclarationSerializer(declaration).data)


class SubmitTaxDeclarationView(APIView):
    """POST /payroll/tax-declarations/me/submit/ — locks the regime choice in
    for HR review. A submitted (not yet approved) declaration can still be
    edited (re-submitting just updates submitted_at), matching how a leave
    request stays editable until an approver actually acts on it."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        declaration, _ = EmployeeTaxDeclaration.objects.get_or_create(
            employee=request.user, financial_year_start=_current_fy_start(),
        )
        if declaration.status == EmployeeTaxDeclaration.STATUS_APPROVED:
            return error('This declaration has already been approved.', http_status=409)
        declaration.status = EmployeeTaxDeclaration.STATUS_SUBMITTED
        declaration.submitted_at = timezone.now()
        declaration.save(update_fields=['status', 'submitted_at', 'updated_at'])
        logger.info('Tax declaration submitted by %s for FY start %s', request.user.email, declaration.financial_year_start)
        return success('Declaration submitted for HR review.', EmployeeTaxDeclarationSerializer(declaration).data)


class TaxDeclarationListView(APIView):
    """GET /payroll/tax-declarations/ — HR queue of every employee's current-FY
    declaration, gated by tax_declarations.approve."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'tax_declarations.approve'):
            return error('Permission denied.', http_status=403)
        status_param = request.query_params.get('status')
        queryset = (
            EmployeeTaxDeclaration.objects
            .filter(financial_year_start=_current_fy_start())
            .select_related('employee', 'approved_by')
        )
        if status_param:
            queryset = queryset.filter(status=status_param)
        return success(
            'Tax declarations retrieved.',
            EmployeeTaxDeclarationSerializer(queryset, many=True).data,
        )


class ApproveTaxDeclarationView(APIView):
    """POST /payroll/tax-declarations/<id>/approve/ — HR review step only;
    does not change any payroll computation (none exists yet — see the
    model's own docstring)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'tax_declarations.approve'):
            return error('Permission denied.', http_status=403)
        try:
            declaration = EmployeeTaxDeclaration.objects.get(pk=pk)
        except EmployeeTaxDeclaration.DoesNotExist:
            return error('Declaration not found.', http_status=404)
        if declaration.status != EmployeeTaxDeclaration.STATUS_SUBMITTED:
            return error('Only a submitted declaration can be approved.', http_status=409)
        declaration.status = EmployeeTaxDeclaration.STATUS_APPROVED
        declaration.approved_at = timezone.now()
        declaration.approved_by = request.user
        declaration.save(update_fields=['status', 'approved_at', 'approved_by', 'updated_at'])
        logger.info('Tax declaration %s approved by %s', declaration.pk, request.user.email)
        return success('Declaration approved.', EmployeeTaxDeclarationSerializer(declaration).data)
