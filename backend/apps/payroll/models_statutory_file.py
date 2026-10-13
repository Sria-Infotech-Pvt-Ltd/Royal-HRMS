"""Phase 7B Task J — statutory returns and challans, same template mechanism as Task H."""
import uuid

from django.db import models


class StatutoryFileTemplate(models.Model):
    SCHEME_ECR  = 'ECR'
    SCHEME_ESIC = 'ESIC'
    SCHEME_CHOICES = [(SCHEME_ECR, 'EPFO — ECR'), (SCHEME_ESIC, 'ESIC')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    scheme = models.CharField(max_length=20, choices=SCHEME_CHOICES)
    field_specs = models.JSONField(default=list, help_text='Same {source, label} shape as BankFileTemplate.field_specs.')
    delimiter = models.CharField(max_length=5, default='#~#')
    file_name_pattern = models.CharField(max_length=200, default='{scheme}_{period_start}_{period_end}.txt')
    requires_uan = models.BooleanField(default=True, help_text='ECR requires UAN per employee — missing UAN blocks generation and is reported, not skipped.')
    is_active = models.BooleanField(default=True)
    note = models.TextField(
        default='Verify against the current official EPFO/ESIC specification before go-live.', blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_statutory_file_templates_v2'
        ordering = ['scheme', 'code']

    def __str__(self):
        return self.code


class GeneratedStatutoryFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(StatutoryFileTemplate, on_delete=models.PROTECT, related_name='generated_files')
    run = models.ForeignKey('payroll.PayrollRun', on_delete=models.CASCADE, null=True, blank=True, related_name='statutory_files')
    file_name = models.CharField(max_length=255)
    content = models.TextField()
    checksum_sha256 = models.CharField(max_length=64)
    missing_identity_employee_ids = models.JSONField(
        default=list, blank=True, help_text='Employees excluded because a required identity document (e.g. UAN) was missing.',
    )
    generated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='statutory_files_generated')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_generated_statutory_files_v2'
        ordering = ['-created_at']

    def __str__(self):
        return self.file_name
