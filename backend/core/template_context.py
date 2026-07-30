"""
Shared email-template variable context builders.

Single source of truth for "what values does this entity resolve to" —
used both by ResolveTemplateVariablesView (apps/accounts/views.py, lets the
approve/reject/decide UI auto-fill template variables before sending) and by
the actual send call sites (e.g. apps/hrms/views/expenses.py) so the preview
a human sees is guaranteed to match what's actually emailed. Keeping this in
one place is what makes it safe — duplicating this logic per call site is
exactly how the "some variables never auto-fill" bug happened in the first
place.
"""
from datetime import date


def company_name() -> str:
    from apps.accounts.models import Company
    company = Company.objects.first()
    return company.company_name if company else ''


def employee_identity_fields(employee) -> dict:
    """FNAME/LNAME/FULL_NAME/EMAIL — universal identity variables shared by
    every template regardless of what entity (leave/expense/...) triggered it."""
    full_name = employee.full_name or ''
    parts     = full_name.strip().split()
    first     = parts[0] if parts else full_name
    last      = parts[-1] if len(parts) > 1 else ''
    lower = {'full_name': full_name, 'first_name': first, 'last_name': last, 'email': employee.email or ''}
    upper = {'FULL_NAME': full_name, 'FNAME': first, 'LNAME': last, 'EMAIL': lower['email']}
    return {**lower, **upper}


def universal_context() -> dict:
    """
    Values that make sense regardless of which entity is being approved —
    e.g. a payslip-style template used from the expense-approval flow asks
    for MONTH/YEAR, which aren't fields on an Expense at all; "the current
    month/year" is the only sane resolution for those variables here.
    """
    today = date.today()
    lower = {
        'date':  today.isoformat(),
        'month': today.strftime('%B'),
        'year':  str(today.year),
    }
    upper = {'DATE': lower['date'], 'MONTH': lower['month'], 'YEAR': lower['year']}
    return {**lower, **upper}


def candidate_context(candidate, actor=None) -> dict:
    from apps.accounts.models import Company

    parts      = candidate.name.strip().split()
    first_name = parts[0] if parts else candidate.name
    last_name  = parts[-1] if len(parts) > 1 else ''
    branch_name = candidate.branch.branch_name if candidate.branch else ''
    mode_display = candidate.get_interview_mode_display() if candidate.interview_mode else ''
    interview_date = candidate.interview_date.isoformat() if candidate.interview_date else ''

    # Once a candidate converts to a real employee (portal_user), the
    # onboarding_* templates' variables live on that User instead of the
    # Candidate — blank (never a raw {var}) if conversion hasn't happened yet.
    employee = candidate.portal_user
    company  = Company.objects.first()
    portal_url = (getattr(company, 'portal_url', '') or '') if company else ''
    assessment_count = candidate.assessment_assignments.filter(
        status__in=['pending', 'in_progress']
    ).count()

    lower = {
        'candidate_name': candidate.name,
        'full_name':      candidate.name,
        'first_name':     first_name,
        'last_name':      last_name,
        'fname':          first_name,
        'lname':          last_name,
        'email':          candidate.email,
        'candidate_email': candidate.email,
        'position_applied': candidate.position_applied,
        'position':          candidate.position_applied,
        'branch':            branch_name,
        'branch_name':       branch_name,
        'interview_date':    interview_date,
        'interview_mode':    candidate.interview_mode or '',
        'interview_mode_display': mode_display,
        'company_name':      company_name(),
        'employee_name':     employee.full_name if employee else candidate.name,
        'employee_id':       employee.employee_id if employee else '',
        'designation':       employee.designation if employee else '',
        'department':        employee.department if employee else '',
        'date_of_joining':   employee.date_of_joining.isoformat() if employee and employee.date_of_joining else '',
        'portal_url':        portal_url,
        'has_assessments':   'yes' if assessment_count else 'no',
        'assessment_count':  str(assessment_count),
        'hr_name':           actor.full_name if actor else '',
    }
    upper = {
        'FULL_NAME': lower['full_name'], 'FNAME': first_name, 'LNAME': last_name,
        'EMAIL': lower['email'], 'POSITION': lower['position'], 'COMPANY': lower['company_name'],
        'EMPLOYEE_ID': lower['employee_id'], 'DEPARTMENT': lower['department'],
        'DESIGNATION': lower['designation'],
    }
    return {**lower, **upper}


def leave_request_context(leave_request) -> dict:
    employee = leave_request.employee
    lower = {
        **employee_identity_fields(employee),
        'employee_name':      employee.full_name or '',
        'employee_code':      employee.employee_id or '',
        'department':         employee.department or '',
        'branch':             employee.branch or '',
        'leave_type':         leave_request.leave_type,
        'leave_type_display': leave_request.get_leave_type_display(),
        'start_date':         leave_request.start_date.isoformat(),
        'end_date':           leave_request.end_date.isoformat(),
        'total_days':         str(leave_request.total_days),
        'reason':             leave_request.reason or '',
        'company_name':       company_name(),
    }
    upper = {
        'EMPLOYEE_NAME': lower['employee_name'], 'EMPLOYEE_ID': lower['employee_code'],
        'LEAVE_TYPE': lower['leave_type_display'],
        'START_DATE': lower['start_date'], 'END_DATE': lower['end_date'],
        'TOTAL_DAYS': lower['total_days'], 'REASON': lower['reason'],
        'COMPANY': lower['company_name'],
    }
    return {**lower, **upper}


def expense_context(expense) -> dict:
    employee = expense.employee
    lower = {
        **employee_identity_fields(employee),
        'employee_name': employee.full_name or '',
        'employee_code': employee.employee_id or '',
        'department':    employee.department or '',
        'branch':        employee.branch or '',
        'category':      expense.get_category_display(),
        'amount':        str(expense.amount),
        'description':   expense.description or '',
        'title':         expense.title,
        'expense_date':  expense.expense_date.isoformat(),
        'expense_number': str(expense.expense_number or ''),
        'company_name':  company_name(),
    }
    upper = {
        'EMPLOYEE_NAME': lower['employee_name'], 'EMPLOYEE_ID': lower['employee_code'],
        'CATEGORY': lower['category'], 'AMOUNT': lower['amount'],
        'DESCRIPTION': lower['description'], 'COMPANY': lower['company_name'],
    }
    return {**lower, **upper}
