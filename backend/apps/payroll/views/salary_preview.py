from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, success
from apps.payroll.models import SalaryStructure, StatutoryConfig
from apps.payroll.services_estimate import estimate_salary_breakdown


class SalaryPreviewView(APIView):
    """Feeds the Hire wizard's Basic Pay step — live estimate only, see
    services_estimate.py's own module docstring for why this is separate
    from the real payroll engine."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'employees.create'):
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
        if branch_id:
            from apps.branch.models import Branch
            branch = Branch.objects.filter(pk=branch_id).first()

        statutory = None
        if branch is not None:
            statutory = StatutoryConfig.objects.filter(state=branch.state).first()

        breakdown = estimate_salary_breakdown(annual_ctc, structure, branch, statutory)
        return success('Salary breakdown estimated.', breakdown)
