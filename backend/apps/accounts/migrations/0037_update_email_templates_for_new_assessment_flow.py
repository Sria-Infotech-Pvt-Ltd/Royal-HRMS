"""
Update email templates to reflect the new assessment flow:
  - Assessments are now assigned AFTER HR approves the onboarding wizard,
    not at portal login time.
  - portal_invite: remove the assessment mention (candidate goes straight to wizard).
  - onboarding_approved: add a section telling the employee to complete assessments
    before accessing the full employment portal.
"""
from django.db import migrations

# ── portal_invite ──────────────────────────────────────────────────────────────

OLD_PORTAL_INVITE_PARAS = (
    '<p>Once you log in, you may be asked to complete a short assessment before '
    'proceeding. The assessment includes a brief video and a few questions to '
    'help us understand your profile better. <strong>Please complete all '
    'assessment tasks first</strong> — the onboarding wizard will unlock '
    'automatically once you are done.</p>'
    '\n\n'
    '<p>After the assessment, the onboarding wizard will guide you through '
    'filling in your personal, educational, and bank details and uploading '
    'required documents.</p>'
)

NEW_PORTAL_INVITE_PARA = (
    '<p>Once you log in, the onboarding wizard will guide you through filling '
    'in your personal, educational, and bank details and uploading the required '
    'documents. Please complete all steps as soon as possible so HR can process '
    'your joining formalities.</p>'
)

# ── onboarding_approved ────────────────────────────────────────────────────────

OLD_APPROVED_CTA = (
    '<p>You can now log in to the employee portal to access your dashboard, '
    'payslips, leave requests, and more.</p>\n\n'
    '<p style="margin:24px 0;">\n'
    '  <a href="{portal_url}"\n'
    '     style="background:#4f46e5;color:#ffffff;padding:12px 28px;\n'
    '            border-radius:6px;text-decoration:none;font-weight:600;">\n'
    '    Go to Employee Portal\n'
    '  </a>\n'
    '</p>'
)

NEW_APPROVED_CTA = (
    '<p>As the next step, please log in to the portal and complete the '
    'assigned assessment(s). <strong>Full access to the employment portal — '
    'including your dashboard, payslips, and leave requests — will be unlocked '
    'once you have completed all assessments.</strong></p>\n\n'
    '<p style="background:#fef9c3;border-left:4px solid #eab308;padding:12px 16px;'
    'border-radius:4px;margin:16px 0;">'
    '&#9888;&nbsp; If you do not clear an assessment on the first attempt, '
    'you can retry it as many times as needed from the portal.</p>\n\n'
    '<p style="margin:24px 0;">\n'
    '  <a href="{portal_url}"\n'
    '     style="background:#4f46e5;color:#ffffff;padding:12px 28px;\n'
    '            border-radius:6px;text-decoration:none;font-weight:600;">\n'
    '    Go to Portal &amp; Complete Assessment\n'
    '  </a>\n'
    '</p>'
)


def update_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')

    # Update portal_invite
    try:
        t = EmailTemplate.objects.get(name='portal_invite')
        if OLD_PORTAL_INVITE_PARAS in t.body:
            t.body = t.body.replace(OLD_PORTAL_INVITE_PARAS, NEW_PORTAL_INVITE_PARA)
            t.save(update_fields=['body'])
    except EmailTemplate.DoesNotExist:
        pass

    # Update onboarding_approved
    try:
        t = EmailTemplate.objects.get(name='onboarding_approved')
        if OLD_APPROVED_CTA in t.body:
            t.body = t.body.replace(OLD_APPROVED_CTA, NEW_APPROVED_CTA)
            t.save(update_fields=['body'])
        # Add new variables to available_variables
        existing = t.available_variables or []
        for var in ('has_assessments', 'assessment_count'):
            if var not in existing:
                existing.append(var)
        t.available_variables = existing
        t.save(update_fields=['available_variables'])
    except EmailTemplate.DoesNotExist:
        pass


def revert_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')

    try:
        t = EmailTemplate.objects.get(name='portal_invite')
        if NEW_PORTAL_INVITE_PARA in t.body:
            t.body = t.body.replace(NEW_PORTAL_INVITE_PARA, OLD_PORTAL_INVITE_PARAS)
            t.save(update_fields=['body'])
    except EmailTemplate.DoesNotExist:
        pass

    try:
        t = EmailTemplate.objects.get(name='onboarding_approved')
        if NEW_APPROVED_CTA in t.body:
            t.body = t.body.replace(NEW_APPROVED_CTA, OLD_APPROVED_CTA)
            t.save(update_fields=['body'])
    except EmailTemplate.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0036_seed_onboarding_submitted_email_template'),
    ]

    operations = [
        migrations.RunPython(update_templates, revert_templates),
    ]
