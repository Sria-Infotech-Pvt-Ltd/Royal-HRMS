"""
Phase 7A Task B — seed PayComponent rows that reproduce, exactly, every
component this company's payroll already uses today: the 3 distinct
SalaryComponent names actually present across every SalaryStructure
(Basic / HRA / Special Allowance — confirmed via
`SalaryComponent.objects.values('name', ...).distinct()` before writing this
command) and every fixed EmployeePayslip column the legacy engine computes.

Idempotent (get_or_create by code, same convention
seed_attendance_lookups/sync_policy_types already use) — safe to re-run.

This command does NOT touch SalaryComponent/SalaryStructure/EmployeePayslip
and nothing reads PayComponent yet — see models_pay_component.py's own
module docstring. Running it is purely additive catalogue data.
"""
from django.core.management.base import BaseCommand

from apps.payroll.models import PayComponent


# code, name, category, calculation_method, base_component_code, payslip_group, show_if_zero
_SEED = [
    # ── Earnings (mirrors today's 3 real SalaryComponent names) ─────────
    dict(code='BASIC', name='Basic', category=PayComponent.CATEGORY_EARNING,
         calculation_method=PayComponent.METHOD_PERCENTAGE, base_component_code='CTC_MONTHLY',
         payslip_group='Earnings', pf_wage_inclusion=True, esi_wage_inclusion=True,
         gratuity_wage_inclusion=True, bonus_wage_inclusion=True),
    dict(code='HRA', name='HRA', category=PayComponent.CATEGORY_EARNING,
         calculation_method=PayComponent.METHOD_PERCENTAGE, base_component_code='CTC_MONTHLY',
         payslip_group='Earnings', tax_section_code='HRA_EXEMPTION',
         esi_wage_inclusion=True),
    dict(code='SPECIAL', name='Special Allowance', category=PayComponent.CATEGORY_EARNING,
         calculation_method=PayComponent.METHOD_PERCENTAGE, base_component_code='CTC_MONTHLY',
         payslip_group='Earnings', esi_wage_inclusion=True),
    dict(code='REIMB', name='Reimbursements', category=PayComponent.CATEGORY_REIMBURSEMENT,
         calculation_method=PayComponent.METHOD_INPUT, is_taxable=False,
         payslip_group='Earnings', is_recurring=False),
    dict(code='BONUS', name='Bonus', category=PayComponent.CATEGORY_EARNING,
         calculation_method=PayComponent.METHOD_INPUT,
         payslip_group='Earnings', is_recurring=False, bonus_wage_inclusion=False),
    dict(code='ADJ_EARN', name='Other Additions', category=PayComponent.CATEGORY_EARNING,
         calculation_method=PayComponent.METHOD_INPUT,
         payslip_group='Earnings', is_recurring=False, is_arrear_eligible=True),

    # ── Statutory deductions ─────────────────────────────────────────────
    dict(code='PF_EE', name='Provident Fund (Employee)', category=PayComponent.CATEGORY_STATUTORY,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         payslip_group='Statutory deductions'),
    dict(code='ESI_EE', name='ESI (Employee)', category=PayComponent.CATEGORY_STATUTORY,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         payslip_group='Statutory deductions'),
    dict(code='PT', name='Professional Tax', category=PayComponent.CATEGORY_STATUTORY,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         payslip_group='Statutory deductions'),
    dict(code='LWF_EE', name='Labour Welfare Fund (Employee)', category=PayComponent.CATEGORY_STATUTORY,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         payslip_group='Statutory deductions'),
    dict(code='TDS', name='Income Tax (TDS)', category=PayComponent.CATEGORY_DEDUCTION,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         payslip_group='Statutory deductions'),
    dict(code='LOP', name='Loss of Pay', category=PayComponent.CATEGORY_DEDUCTION,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         proration=PayComponent.PRORATION_PAID_DAYS, affected_by_lop=True,
         payslip_group='Other deductions'),
    dict(code='ADJ_DED', name='Other Deductions', category=PayComponent.CATEGORY_DEDUCTION,
         calculation_method=PayComponent.METHOD_INPUT, is_taxable=False,
         payslip_group='Other deductions', is_recurring=False),

    # ── Employer contributions (not deducted from the employee) ─────────
    dict(code='PF_ER', name='Provident Fund (Employer)', category=PayComponent.CATEGORY_EMPLOYER_CONTRIBUTION,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         payslip_group='Employer contributions', show_on_payslip=False),
    dict(code='ESI_ER', name='ESI (Employer)', category=PayComponent.CATEGORY_EMPLOYER_CONTRIBUTION,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         payslip_group='Employer contributions', show_on_payslip=False),
    dict(code='LWF_ER', name='Labour Welfare Fund (Employer)', category=PayComponent.CATEGORY_EMPLOYER_CONTRIBUTION,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         payslip_group='Employer contributions', show_on_payslip=False),

    # ── Informational totals (fixed EmployeePayslip columns with no
    #    component of their own today — kept as PayComponent rows purely so
    #    Task E's payslip-lines mapping has a code for every stored column) ──
    dict(code='GROSS_EARNINGS', name='Gross Earnings', category=PayComponent.CATEGORY_INFORMATIONAL,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         payslip_group='Summary'),
    dict(code='NET_PAY', name='Net Pay', category=PayComponent.CATEGORY_NET_PAY,
         calculation_method=PayComponent.METHOD_SYSTEM, is_taxable=False,
         payslip_group='Summary'),
]


class Command(BaseCommand):
    help = 'Phase 7A Task B — seed the PayComponent master catalogue (idempotent, additive, read by nothing yet).'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for i, spec in enumerate(_SEED):
            spec = {**spec, 'display_order': spec.get('display_order', i * 10), 'status': PayComponent.STATUS_PUBLISHED}
            code = spec.pop('code')
            obj, was_created = PayComponent.objects.update_or_create(code=code, defaults=spec)
            created += int(was_created)
            updated += int(not was_created)
        self.stdout.write(self.style.SUCCESS(
            f'PayComponent seed complete — created={created} updated={updated} (total {len(_SEED)}).'
        ))
