"""
Phase 7A Task H — tax declaration windows and per-section proof review.

`EmployeeTaxDeclaration.declared_investments` (the real, live JSON field the
legacy engine reads) is left completely untouched — these are additive
structures alongside it: `TaxDeclarationWindow` configures when declarations/
proofs are open per financial year, `TaxProofSubmission` tracks per-section
review (declared vs. approved amount, with remarks) for a declaration.

Deferred, stated plainly (see Phase 7A Task H report): the 3B
workflow/approval wiring and window-open/close reminder events are NOT
built in this pass — these models and the section-mapping report
(services_tax_declaration.py) are the data layer Task H asks for; wiring
them into an actual review workflow and reminder schedule is real workflow-
integration work with its own scope, not mechanical scaffolding.
"""
import uuid

from django.db import models


class TaxDeclarationWindow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    financial_year_start = models.PositiveIntegerField()
    legal_entity = models.ForeignKey(
        'platform_core.LegalEntity', on_delete=models.CASCADE, null=True, blank=True,
        related_name='tax_declaration_windows',
        help_text='Blank = applies to every legal entity.',
    )
    declaration_open_from = models.DateField()
    declaration_open_to = models.DateField()
    proof_open_from = models.DateField()
    proof_open_to = models.DateField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_tax_declaration_windows_v2'
        unique_together = [('financial_year_start', 'legal_entity')]
        ordering = ['-financial_year_start']

    def __str__(self):
        scope = self.legal_entity.code if self.legal_entity_id else 'all entities'
        return f'FY{self.financial_year_start} window ({scope})'

    def declaration_is_open(self, as_of_date) -> bool:
        return self.is_active and self.declaration_open_from <= as_of_date <= self.declaration_open_to

    def proof_is_open(self, as_of_date) -> bool:
        return self.is_active and self.proof_open_from <= as_of_date <= self.proof_open_to


class TaxProofSubmission(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING,  'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    declaration = models.ForeignKey(
        'payroll.EmployeeTaxDeclaration', on_delete=models.CASCADE, related_name='proof_submissions',
    )
    section_code = models.CharField(max_length=20, help_text='TaxSection.code this proof is for.')
    declared_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    document = models.ForeignKey(
        'accounts.EmployeeDocument', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tax_proof_submissions',
        help_text='The uploaded proof file, reusing the existing employee-documents model — no new upload pipeline.',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    remarks = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tax_proofs_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_tax_proof_submissions_v2'
        unique_together = [('declaration', 'section_code')]
        ordering = ['section_code']

    def __str__(self):
        return f'{self.declaration_id} › {self.section_code} ({self.status})'
