"""
Backfill the "onboarding_approved" EmailTemplate row.

0025_company_portal_url_and_onboarding_email_templates.py seeded it via
get_or_create alongside "onboarding_rejected", and both are marked applied —
but only "onboarding_rejected" actually exists in this database; someone
evidently deleted the "onboarding_approved" row afterward (e.g. via
Settings -> Email Templates), most likely during testing. Nothing re-creates
a deleted row on its own, since migrations only run their RunPython once.

0037_update_email_templates_for_new_assessment_flow.py, which patches this
template's CTA copy for the newer assessment-first flow, wraps its lookup in
try/except EmailTemplate.DoesNotExist: pass — so it silently no-op'd instead
of failing when the row was already missing by the time it ran. That's why
`showmigrations` shows both 0025 and 0037 as cleanly applied even though the
row was never actually there for anyone to use.

The result: apps.accounts.utils.send_template_email('onboarding_approved', ...)
(called from OnboardingApprovalView.post — apps/accounts/views.py) raised
LookupError on every onboarding approval, so the "you're approved, welcome"
email never sent.

This recreates the row with the FINAL content 0025 + 0037 together intended
(the assessment-first CTA and its two extra template variables), not 0025's
now-superseded original copy.
"""
from django.db import migrations

ONBOARDING_APPROVED_BODY = """<p>Dear {employee_name},</p>

<p>We are delighted to welcome you to <strong>{company_name}</strong>!</p>

<p>Your onboarding has been reviewed and <strong>approved</strong> by HR. You are now an official member of our team.</p>

<table style="border-collapse:collapse;margin:16px 0;">
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Employee ID</td>
    <td style="padding:6px 12px;font-family:monospace;">{employee_id}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Designation</td>
    <td style="padding:6px 12px;">{designation}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Department</td>
    <td style="padding:6px 12px;">{department}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Date of Joining</td>
    <td style="padding:6px 12px;">{date_of_joining}</td>
  </tr>
</table>

<p>As the next step, please log in to the portal and complete the assigned assessment(s). <strong>Full access to the employment portal — including your dashboard, payslips, and leave requests — will be unlocked once you have completed all assessments.</strong></p>

<p style="background:#fef9c3;border-left:4px solid #eab308;padding:12px 16px;border-radius:4px;margin:16px 0;">&#9888;&nbsp; If you do not clear an assessment on the first attempt, you can retry it as many times as needed from the portal.</p>

<p style="margin:24px 0;">
  <a href="{portal_url}"
     style="background:#4f46e5;color:#ffffff;padding:12px 28px;
            border-radius:6px;text-decoration:none;font-weight:600;">
    Go to Portal &amp; Complete Assessment
  </a>
</p>

<p>If you have any questions, please reach out to the HR team.</p>

<p>Welcome aboard!<br/><strong>HR Team — {company_name}</strong></p>"""


def seed_forward(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')

    EmailTemplate.objects.get_or_create(
        name='onboarding_approved',
        defaults={
            'display_name':        'Onboarding Approved — Welcome Email',
            'description':         'Sent to the employee after HR approves their onboarding submission.',
            'template_type':       'onboarding',
            'subject':             'Welcome to {company_name} — Onboarding Approved',
            'body':                ONBOARDING_APPROVED_BODY,
            'is_active':           True,
            'is_builtin':          False,
            'available_variables': [
                'employee_name', 'company_name', 'employee_id',
                'designation', 'department', 'date_of_joining', 'portal_url',
                'has_assessments', 'assessment_count',
            ],
        },
    )


def seed_reverse(apps, schema_editor):
    # No-op: this is a backfill for a row that went missing through no fault
    # of the migration history — reversing would just re-break onboarding
    # approval emails.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0056_widen_employee_document_file_field'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
