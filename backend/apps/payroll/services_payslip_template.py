"""
Phase 7B Task K — payslip templates. Produces the STRUCTURED DATA a PDF
renderer needs (sections of PayslipLine rows grouped by payslip_group, YTD
figures from Phase 7A Task E), using only the real PayComponent catalogue
— no template-string execution of any kind (section_order is a plain list
of group names, matched by equality, never interpolated into a template
engine).

Deferred, stated plainly: actual PDF rendering (reusing the existing PDF
stack, per the master prompt) and the email-distribution/password-
protection wiring are NOT built in this pass — this produces the render-
ready data dict only. `render_password()` implements the password RULE
(so a real send can call it later) without this pass actually sending
anything.
"""
import hashlib

from apps.payroll.models import PayComponent


def render_payslip_data(template, payslip) -> dict:
    lines_by_group = {}
    component_group_by_code = dict(PayComponent.objects.values_list('code', 'payslip_group'))

    for line in payslip.lines.all().order_by('display_order', 'component_code'):
        group = component_group_by_code.get(line.component_code, 'Other')
        lines_by_group.setdefault(group, []).append({
            'component_code': line.component_code, 'amount': line.amount, 'ytd_amount': line.ytd_amount,
        })

    sections = [
        {'group': group, 'lines': lines_by_group.get(group, [])}
        for group in (template.section_order or sorted(lines_by_group))
    ]

    return {
        'template_code': template.code,
        'employee_id': payslip.employee.employee_id,
        'cycle_start': payslip.cycle.cycle_start,
        'cycle_end': payslip.cycle.cycle_end,
        'sections': sections,
        'show_ytd': template.show_ytd,
        'net_pay': payslip.net_pay,
    }


def render_password(template, employee) -> str:
    """Resolves template.password_rule into an actual password string.
    Only the 'dob_ddmmyyyy+pan_last4' rule (this template's own default) is
    implemented; any other rule string raises rather than silently
    returning something wrong."""
    if template.password_rule != 'dob_ddmmyyyy+pan_last4':
        raise ValueError(f'Unsupported password_rule: {template.password_rule!r}')

    profile = getattr(employee, 'profile', None)
    dob = getattr(profile, 'date_of_birth', None)
    pan = getattr(profile, 'pan_number', '') or ''
    if dob is None:
        raise ValueError(f'{employee}: no date_of_birth on file — cannot derive the payslip password.')

    dob_part = dob.strftime('%d%m%Y')
    pan_part = pan[-4:] if len(pan) >= 4 else pan
    return f'{dob_part}{pan_part}'


def password_hint_hash(password: str) -> str:
    """Never log/store the real password — only a hash, for verifying
    "was this the password we generated" without keeping the plaintext."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()
