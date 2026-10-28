from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, success
from apps.payroll.models import SalaryStructure, StatutoryConfig
from apps.payroll.services_estimate import estimate_salary_breakdown


class SalaryPreviewView(APIView):
    """Feeds the Hire wizard's Basic Pay step AND the Employee Directory's
    Basic pay dialog (useBasicPayEditor.ts) — live estimate only, see
    services_estimate.py's own module docstring for why this is separate
    from the real payroll engine."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # employees.create: the Hire wizard, previewing pay for someone not
        # hired yet. payroll.edit: HR/Payroll editing an existing employee's
        # Basic pay record. Either is enough to preview a breakdown.
        if not (_has_perm(request.user, 'employees.create') or _has_perm(request.user, 'payroll.edit')):
            return error('You do not have permission to perform this action.', http_status=403)

        annual_ctc = request.data.get('annual_ctc')
        if not annual_ctc:
            return error('Annual CTC is required.')
        try:
            annual_ctc = float(annual_ctc)
        except (TypeError, ValueError):
            return error('Annual CTC must be a number.')

        structure = None
        structure_id = request.data.get('salary_structure')
        if structure_id:
            structure = SalaryStructure.objects.filter(pk=structure_id, is_active=True).first()

        branch = None
        branch_id = request.data.get('branch')
        branch_name = request.data.get('branch_name')
        if branch_id or branch_name:
            from apps.branch.models import Branch
            if branch_id:
                branch = Branch.objects.filter(pk=branch_id).first()
            # The Basic pay dialog (useBasicPayEditor.ts) only has the
            # employee's branch NAME on hand (Employee.branch is a name
            # string, not a Branch id) — fall back to that so metro-HRA/PT
            # still resolve correctly without the frontend needing to chase
            # down a UUID it doesn't otherwise use.
            if branch is None and branch_name:
                branch = Branch.objects.filter(branch_name=branch_name).first()

        statutory = None
        if branch is not None:
            statutory = StatutoryConfig.objects.filter(state=branch.state).first()

        overrides = request.data.get('earnings_override') or None
        if overrides is not None and not isinstance(overrides, dict):
            return error('earnings_override must be an object.')

        basic_percent = request.data.get('basic_percent')

        breakdown = estimate_salary_breakdown(
            annual_ctc, structure, branch, statutory, overrides=overrides, basic_percent=basic_percent,
        )
        return success('Salary breakdown estimated.', breakdown)
