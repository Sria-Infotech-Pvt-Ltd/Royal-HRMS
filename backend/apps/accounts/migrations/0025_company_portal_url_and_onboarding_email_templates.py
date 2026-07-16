from django.db import migrations, models


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

<p>You can now log in to the employee portal to access your dashboard, payslips, leave requests, and more.</p>

<p style="margin:24px 0;">
  <a href="{portal_url}"
     style="background:#4f46e5;color:#ffffff;padding:12px 28px;
            border-radius:6px;text-decoration:none;font-weight:600;">
    Go to Employee Portal
  </a>
</p>

<p>If you have any questions, please reach out to the HR team.</p>

<p>Welcome aboard!<br/><strong>HR Team — {company_name}</strong></p>"""


ONBOARDING_REJECTED_BODY = """<p>Dear {employee_name},</p>

<p>Thank you for completing your onboarding profile with <strong>{company_name}</strong>.</p>

<p>After reviewing your submission, HR has requested some corrections before your profile can be approved. Please log back into the portal and address the points below:</p>

<blockquote style="border-left:4px solid #e5e7eb;margin:16px 0;padding:12px 20px;
                   background:#f9fafb;color:#374151;border-radius:4px;">
  {remarks}
</blockquote>

<p>Once you have made the necessary updates, please re-submit your onboarding form so HR can process your joining formalities.</p>

<p style="margin:24px 0;">
  <a href="{portal_url}"
     style="background:#4f46e5;color:#ffffff;padding:12px 28px;
            border-radius:6px;text-decoration:none;font-weight:600;">
    Return to Onboarding Portal
  </a>
</p>

<p>If you have any questions, please contact HR directly.</p>

<p>Regards,<br/><strong>HR Team — {company_name}</strong></p>"""


def seed_onboarding_email_templates(apps, schema_editor):
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
            ],
        },
    )

    EmailTemplate.objects.get_or_create(
        name='onboarding_rejected',
        defaults={
            'display_name':        'Onboarding Returned for Corrections',
            'description':         'Sent to the employee when HR sends the onboarding back for corrections.',
            'template_type':       'onboarding',
            'subject':             'Action Required: Please Update Your Onboarding Profile — {company_name}',
            'body':                ONBOARDING_REJECTED_BODY,
            'is_active':           True,
            'is_builtin':          False,
            'available_variables': [
                'employee_name', 'company_name', 'remarks', 'portal_url',
            ],
        },
    )


def reverse_seed(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(
        name__in=['onboarding_approved', 'onboarding_rejected']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_employee_doc_upload_path"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="portal_url",
            field=models.CharField(
                blank=True,
                help_text="Employee onboarding portal URL sent in invitation emails.",
                max_length=255,
            ),
        ),
        migrations.RunPython(
            seed_onboarding_email_templates,
            reverse_seed,
        ),
    ]
