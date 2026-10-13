"""
Phase 7A Task I — calculation trace and explainability.

Reads PayslipLine.calculation_basis (Task E) — no new trace storage, since
every line already carries a compact, identity-free basis dict. This module
turns that into a plain-language sentence per line ("explain this
payslip") and a line-by-line diff between two payslips ("explain the
difference"). No identity data is read or surfaced — only component codes
and amounts, same rule Task E's own basis dicts already follow.
"""
from decimal import Decimal


_COLUMN_PHRASES = {
    'basic': 'the Basic component as computed by the salary structure',
    'hra': 'the HRA component as computed by the salary structure',
    'special_allowance': 'the Special Allowance component as computed by the salary structure',
    'reimbursements': 'approved reimbursements for this cycle',
    'bonus': 'bonus amounts recorded for this cycle',
    'gross_earnings': 'the sum of every earning component this cycle',
    'lop_deduction': 'a Loss-of-Pay deduction based on days absent',
    'pf_employee': "the employee's Provident Fund contribution",
    'pf_employer': "the employer's Provident Fund contribution",
    'esi_employee': "the employee's ESI contribution",
    'esi_employer': "the employer's ESI contribution",
    'pt_deduction': 'Professional Tax for the employee\'s state',
    'lwf_employee': "the employee's Labour Welfare Fund contribution",
    'lwf_employer': "the employer's Labour Welfare Fund contribution",
    'income_tax': 'estimated monthly TDS from the income-tax engine',
    'adjustments_earning': 'one-time additions/arrears recorded for this cycle',
    'adjustments_deduction': 'one-time deductions recorded for this cycle',
    'net_pay': 'gross earnings plus adjustments, minus every deduction',
    'other_earnings': 'a custom earning component from the salary structure',
}


def explain_line(line) -> str:
    """One plain-English sentence for a single PayslipLine, built from its
    calculation_basis — never from identity data (the basis dict only ever
    holds column names and numeric inputs, per Task E's own contract)."""
    basis = line.calculation_basis or {}
    column = basis.get('column')
    phrase = _COLUMN_PHRASES.get(column, f'the {column} column' if column else 'this component')

    sentence = f'{line.component_code} = {line.amount} — {phrase}.'

    extra_bits = []
    if 'pf_wage_base' in basis:
        extra_bits.append(f"PF wage base used: {basis['pf_wage_base']}")
    if 'lop_days' in basis and 'total_working_days' in basis:
        extra_bits.append(f"{basis['lop_days']} LOP day(s) out of {basis['total_working_days']} working days")
    if 'original_name' in basis:
        extra_bits.append(f"originally labelled \"{basis['original_name']}\" on the salary structure")
    if extra_bits:
        sentence += ' (' + '; '.join(extra_bits) + ')'

    return sentence


def explain_payslip(payslip) -> list:
    """Every line on `payslip`, in display order, with a plain-language
    explanation. Returns [] if Task E's backfill hasn't been run for this
    payslip yet — this reads PayslipLine, it doesn't compute anything."""
    return [
        {
            'component_code': line.component_code,
            'amount': line.amount,
            'ytd_amount': line.ytd_amount,
            'explanation': explain_line(line),
        }
        for line in payslip.lines.all().order_by('display_order', 'component_code')
    ]


def explain_difference(payslip_a, payslip_b) -> dict:
    """Line-by-line diff between two payslips for the same employee (e.g.
    this month vs. last month) — which components changed, by how much,
    and which calculation_basis keys differ. Amount-only comparison; a line
    present on one side and missing on the other is reported with the
    missing side as None/zero."""
    lines_a = {l.component_code: l for l in payslip_a.lines.all()}
    lines_b = {l.component_code: l for l in payslip_b.lines.all()}

    changes = {}
    for code in sorted(set(lines_a) | set(lines_b)):
        line_a = lines_a.get(code)
        line_b = lines_b.get(code)
        before = line_a.amount if line_a else Decimal('0')
        after = line_b.amount if line_b else Decimal('0')
        if before == after:
            continue

        basis_a = line_a.calculation_basis if line_a else {}
        basis_b = line_b.calculation_basis if line_b else {}
        changed_basis_keys = sorted({
            key for key in set(basis_a) | set(basis_b)
            if basis_a.get(key) != basis_b.get(key)
        })

        changes[code] = {
            'before': before, 'after': after, 'delta': after - before,
            'changed_basis_keys': changed_basis_keys,
        }

    return changes
