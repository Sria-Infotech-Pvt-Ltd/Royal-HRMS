"""
Phase 7B Task H — bank file templates. Scoped down from the master
prompt's full header/detail/footer record-definition language to a single
flat field-list per template (`field_specs`, ordered list of
{source, label, width, pad, align} dicts) rendered by
services_bank_template.py's sandboxed renderer (safe attribute lookups and
formatting only — no eval/exec on template content, see that module).
CSV only in this pass; fixed-width/XLSX/XML are documented as deferred.
"""
import uuid

from django.db import models


class BankFileTemplate(models.Model):
    FORMAT_CSV = 'csv'
    FORMAT_CHOICES = [(FORMAT_CSV, 'CSV')]  # fixed-width/XLSX/XML deferred, see module docstring

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    bank_name = models.CharField(max_length=100)
    file_format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default=FORMAT_CSV)
    # [{"source": "employee.employee_id", "label": "Employee Code"}, ...]
    # `source` is a dotted path resolved by a whitelisted attribute walker
    # — never Python eval(). See services_bank_template.SAFE_SOURCES.
    field_specs = models.JSONField(default=list)
    file_name_pattern = models.CharField(max_length=200, default='salary_transfer_{run_reference}.csv')
    delimiter = models.CharField(max_length=5, default=',')
    include_header_row = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_bank_file_templates_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class GeneratedBankFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(BankFileTemplate, on_delete=models.PROTECT, related_name='generated_files')
    run = models.ForeignKey('payroll.PayrollRun', on_delete=models.CASCADE, related_name='bank_files')
    version = models.PositiveIntegerField(default=1)
    file_name = models.CharField(max_length=255)
    content = models.TextField(help_text='Rendered file content — stored inline for this pass; private blob storage is a deferred Task H follow-up.')
    checksum_sha256 = models.CharField(max_length=64)
    control_total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    control_total_count = models.PositiveIntegerField()
    regeneration_reason = models.CharField(max_length=300, blank=True)
    generated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_files_generated')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_generated_bank_files_v2'
        unique_together = [('run', 'template', 'version')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.file_name} v{self.version}'


class BankFileDownloadLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generated_file = models.ForeignKey(GeneratedBankFile, on_delete=models.CASCADE, related_name='download_logs')
    downloaded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_file_downloads')
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_bank_file_download_logs_v2'
        ordering = ['-downloaded_at']
