from django.db import migrations

# 0006_email_templates hardcoded 'Royal Staffing'/'Royal Staffing Services' into
# 8 built-in templates' subject/body instead of using the {COMPANY} placeholder
# every one of them already lists in available_variables (and that every real
# caller already passes — see apps.accounts.utils.send_template_email). Every
# company using these unedited built-ins was emailing its own employees
# sign-offs naming a different company. Swapping the literal text for
# {COMPANY} here (rather than another hardcoded name) makes these emails
# correct for whichever company is actually configured, matching how every
# other template in this table already works.
_AFFECTED_TEMPLATES = [
    'payslip', 'confirmation_date', 'date_of_joining', 'date_of_retirement',
    'birthday', 'marriage_anniversary', 'onboarding', 'work_anniversary',
]


def fix_hardcoded_company_name(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    for tpl in EmailTemplate.objects.filter(name__in=_AFFECTED_TEMPLATES):
        subject = tpl.subject.replace('Royal Staffing Services', '{COMPANY}').replace('Royal Staffing', '{COMPANY}')
        body    = tpl.body.replace('Royal Staffing Services', '{COMPANY}').replace('Royal Staffing', '{COMPANY}')
        if subject != tpl.subject or body != tpl.body:
            tpl.subject = subject
            tpl.body    = body
            tpl.save(update_fields=['subject', 'body'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0094_add_facial_recognition_approve'),
    ]

    operations = [
        migrations.RunPython(fix_hardcoded_company_name, noop),
    ]
