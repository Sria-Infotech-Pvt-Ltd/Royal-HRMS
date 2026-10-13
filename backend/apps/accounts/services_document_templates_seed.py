"""
Phase 9A Task F — seed the employment-verification letter as a real
DocumentTemplate, reproducing services_employment_letter.py's text
content exactly (confirmed line-by-line against that file before writing
this). `services_employment_letter.render_employment_letter_pdf` is
COMPLETELY UNTOUCHED — this is a parallel, data-driven text version for
the new engine to prove parity against, not a replacement.

Layout note, stated per Task F.3's own "document any differences": the
reportlab PDF has letterhead/signature-table/footer styling this plain
{{variable}} text template doesn't attempt to reproduce — only the BODY
paragraph TEXT is reproduced exactly. Full visual parity would need the
template engine to also carry reportlab layout directives, which is real,
separate scope.
"""
from apps.platform_core.models import DocumentTemplate

EMPLOYMENT_LETTER_BODY = (
    'This is to certify that <b>{{employee_full_name}}</b> '
    '(Employee ID: <b>{{employee_id}}</b>) {{employment_status_clause}}\n\n'
    '{{employee_full_name}} holds the designation of <b>{{designation}}</b> in the '
    '<b>{{department}}</b> department, and joined the organisation on <b>{{joining_date}}</b>.\n\n'
    "This letter is issued upon the employee's request for verification purposes such as "
    'banking, visa or tenancy applications, and may be relied upon accordingly.'
)

EMPLOYMENT_LETTER_VARIABLES = [
    'employee_full_name', 'employee_id', 'employment_status_clause', 'designation', 'department', 'joining_date',
]


def status_clause(employee) -> str:
    """Byte-for-byte the same two sentences
    render_employment_letter_pdf._employment_status_statement() produces."""
    if not employee.is_active:
        return 'is no longer an active employee of the company as of the date of this letter.'
    return f'is currently an active employee of the company, presently in {employee.get_employment_status_display()} status.'


def seed_employment_letter_template() -> DocumentTemplate:
    template, _ = DocumentTemplate.objects.update_or_create(
        code='EMPLOYMENT_VERIFICATION_LETTER', version=1,
        defaults={
            'name': 'Employment Verification Letter', 'document_type': 'employment_verification_letter',
            'declared_variables': EMPLOYMENT_LETTER_VARIABLES, 'body': EMPLOYMENT_LETTER_BODY,
            'status': DocumentTemplate.STATUS_PUBLISHED,
        },
    )
    return template


def build_employment_letter_context(employee) -> dict:
    return {
        'employee_full_name': employee.full_name,
        'employee_id': employee.employee_id or 'not on record',
        'employment_status_clause': status_clause(employee),
        'designation': employee.designation or 'not on record',
        'department': employee.department or 'not on record',
        'joining_date': employee.date_of_joining.strftime('%d %B %Y') if employee.date_of_joining else 'not on record',
    }
