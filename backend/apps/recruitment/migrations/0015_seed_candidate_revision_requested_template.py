"""
Seed the candidate_revision_requested email template.

CandidateHRDecisionView.patch's "reject" branch (backend/apps/recruitment/views.py,
CandidateHRDecisionView) previously had no candidate-facing template at all for
an HR revision request — the candidate was left with no email while the code's
own comment documented the gap. Mirrors the shape of
0010_candidate_selected_rejected_email_templates.py.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'candidate_revision_requested',
        'display_name': 'Candidate — Revision Requested',
        'description':  'Sent to a candidate when HR sends their application/documents back for revision.',
        'template_type': 'recruitment',
        'subject':      'Action needed on your application — {company_name}',
        'body': (
            '<p>Dear {candidate_name},</p>'
            '<p>Thank you for your application for the <strong>{position_applied}</strong> role '
            'at <strong>{company_name}</strong>.</p>'
            '<p>Our HR team has reviewed your submission and needs a few things revisited '
            'before we can proceed further:</p>'
            '<p style="padding:12px 16px;background:#f8f9fa;border-left:3px solid #d97706;">{remarks}</p>'
            '<p>Please get in touch with HR at your earliest convenience to resolve this.</p>'
            '<p style="color:#888;font-size:13px;">Branch: {branch_name}</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'candidate_name', 'position_applied', 'branch_name', 'remarks', 'company_name',
        ],
    },
]


def seed_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    for tpl in _TEMPLATES:
        EmailTemplate.objects.get_or_create(
            name=tpl['name'],
            defaults={k: v for k, v in tpl.items() if k != 'name'},
        )


def remove_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name__in=[t['name'] for t in _TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0014_fix_meeting_link_not_null'),
        ('accounts',    '0135_rename_branch_admin_display_name'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
