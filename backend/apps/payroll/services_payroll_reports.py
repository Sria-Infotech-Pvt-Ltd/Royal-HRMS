"""
Phase 7B Task N — reports. Scoped down to 3 of the master prompt's full
list (payroll register, variance, headcount/cost trend) — real, working,
read-only queries over real data (EmployeePayslip/PayslipLine); the
remaining report types (loan outstanding, arrears register, hold list,
bank payment status, statutory registers, CTC report, YTD earnings, tax
projection) are each a straightforward variation on these same patterns,
not built individually in this pass. None are scope-filtered/field-secured
beyond whatever permission already gates the view that will eventually
call these — that wiring is a frontend/view-layer task, not this service
layer's job.
"""
from decimal import Decimal


def payroll_register(cycle) -> list:
    """One row per payslip in `cycle` — the base data every other register
    report is a filter/aggregation of."""
    rows = []
    for payslip in cycle.payslips.select_related('employee').all():
        rows.append({
            'employee_id': payslip.employee.employee_id, 'employee_name': payslip.employee.full_name,
            'gross_earnings': payslip.gross_earnings, 'total_deductions': payslip.total_deductions,
            'net_pay': payslip.net_pay,
        })
    return rows


def variance_report(cycle_a, cycle_b) -> list:
    """Per-employee net_pay variance between two cycles (e.g. this month
    vs. last)."""
    by_employee_a = {p.employee_id: p for p in cycle_a.payslips.all()}
    by_employee_b = {p.employee_id: p for p in cycle_b.payslips.all()}

    rows = []
    for employee_id in set(by_employee_a) | set(by_employee_b):
        a = by_employee_a.get(employee_id)
        b = by_employee_b.get(employee_id)
        net_a = a.net_pay if a else Decimal('0')
        net_b = b.net_pay if b else Decimal('0')
        if net_a != net_b:
            rows.append({'employee_id': employee_id, 'before': net_a, 'after': net_b, 'delta': net_b - net_a})
    return rows


def headcount_cost_trend(pay_group) -> list:
    """One row per cycle linked to `pay_group` — headcount and total gross
    cost, oldest first."""
    rows = []
    for cycle in pay_group.cycles.order_by('cycle_start').prefetch_related('payslips'):
        payslips = list(cycle.payslips.all())
        rows.append({
            'cycle_start': cycle.cycle_start, 'headcount': len(payslips),
            'total_gross': sum((p.gross_earnings for p in payslips), Decimal('0')),
            'total_net': sum((p.net_pay for p in payslips), Decimal('0')),
        })
    return rows
