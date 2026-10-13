"""
Phase 7B Task K — payslip templates. Scoped down: a layout DEFINITION
(section/group list referencing Task B's PayComponent.payslip_group) +
password-protection config, consumed by services_payslip_template.py to
produce the structured DATA a PDF renderer would need. Actual PDF
rendering/distribution email wiring is deferred — see that module's
docstring.
"""
import uuid

from django.db import models


class PayslipTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.CASCADE, null=True, blank=True, related_name='payslip_templates')
    pay_group = models.ForeignKey('payroll.PayGroup', on_delete=models.CASCADE, null=True, blank=True, related_name='payslip_templates')
    section_order = models.JSONField(
        default=list, help_text='Ordered list of payslip_group names (PayComponent.payslip_group) to render as sections.',
    )
    show_ytd = models.BooleanField(default=True)
    password_protect_email = models.BooleanField(default=False)
    # A rule description, e.g. "dob_ddmmyyyy+pan_last4" — resolved by
    # services_payslip_template.render_password(), never two different
    # emails sent at once (the password is never emailed in the same
    # message as the PDF — enforced by that service, not just documented).
    password_rule = models.CharField(max_length=100, blank=True, default='dob_ddmmyyyy+pan_last4')
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_payslip_templates_v2'
        ordering = ['code']

    def __str__(self):
        return self.code
