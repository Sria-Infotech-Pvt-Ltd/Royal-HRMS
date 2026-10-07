"""
Phase 5A Tasks D+E — identity documents and bank accounts. Reuses the
EXISTING encryption primitives (core.encrypted_fields) — never a second
encryption implementation. Additive: EmployeeProfile's existing
encrypted PAN/Aadhaar/bank fields are kept and kept in sync (Task L) —
NOT executed in this pass, see PHASE5A_REPORT.md.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from core.encrypted_fields import EncryptedCharField


class IdentityDocumentType(models.Model):
    """Country-pack master (Task D.1). `is_sensitive`/`mask_pattern`
    feed Phase 4 field-level security defaults; marked explicitly
    'verify before go-live' in the India seed pack per the prompt's own
    instruction for anything encoding a legal format."""
    UNIQUE_SCOPE_GLOBAL = 'global'
    UNIQUE_SCOPE_LEGAL_ENTITY = 'legal_entity'
    UNIQUE_SCOPE_NONE = 'none'
    UNIQUE_SCOPE_CHOICES = [
        (UNIQUE_SCOPE_GLOBAL, 'Global'), (UNIQUE_SCOPE_LEGAL_ENTITY, 'Per legal entity'), (UNIQUE_SCOPE_NONE, 'Not unique'),
    ]
    NORMALISATION_NONE = 'none'
    NORMALISATION_UPPERCASE = 'uppercase'
    NORMALISATION_STRIP_SPACES = 'strip_spaces'
    NORMALISATION_UPPERCASE_STRIP = 'uppercase_strip_spaces'
    NORMALISATION_CHOICES = [
        (NORMALISATION_NONE, 'None'), (NORMALISATION_UPPERCASE, 'Uppercase'),
        (NORMALISATION_STRIP_SPACES, 'Strip spaces'), (NORMALISATION_UPPERCASE_STRIP, 'Uppercase + strip spaces'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True)
    country = models.ForeignKey('platform_core.Country', on_delete=models.PROTECT, related_name='+')
    label = models.CharField(max_length=100)
    number_regex = models.CharField(max_length=255, blank=True)
    is_sensitive = models.BooleanField(default=True)
    mask_pattern = models.CharField(max_length=50, blank=True, default='***{last4}', help_text='Task D.1 — how a masked value should render.')
    has_expiry = models.BooleanField(default=False)
    requires_attachment = models.BooleanField(default=False)
    unique_scope = models.CharField(max_length=20, choices=UNIQUE_SCOPE_CHOICES, default=UNIQUE_SCOPE_NONE)
    normalisation = models.CharField(max_length=30, choices=NORMALISATION_CHOICES, default=NORMALISATION_NONE)
    is_verified_format = models.BooleanField(default=False, help_text='False = seeded as a placeholder, "verify before go-live" per Task D.1.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_identity_document_types'
        ordering = ['country', 'label']

    def __str__(self):
        return f'{self.country_id}:{self.label}'


class IdentityDocument(models.Model):
    VERIFICATION_PENDING = 'pending'
    VERIFICATION_VERIFIED = 'verified'
    VERIFICATION_REJECTED = 'rejected'
    VERIFICATION_CHOICES = [(VERIFICATION_PENDING, 'Pending'), (VERIFICATION_VERIFIED, 'Verified'), (VERIFICATION_REJECTED, 'Rejected')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE, related_name='+', help_text='employee (User) or family member (FamilyMember).')
    object_id = models.CharField(max_length=64)
    type = models.ForeignKey(IdentityDocumentType, on_delete=models.PROTECT, related_name='documents')

    number = EncryptedCharField(max_length=500, blank=True)
    number_hash = models.CharField(max_length=64, blank=True, db_index=True, help_text='Blind index per type (Task D.2) — replaces pan_number_hash-style uniqueness.')
    name_on_document = EncryptedCharField(max_length=500, blank=True)

    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    issuing_country = models.ForeignKey('platform_core.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    issuing_authority = models.CharField(max_length=150, blank=True)
    place_of_issue = models.CharField(max_length=150, blank=True)

    verification_status = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default=VERIFICATION_PENDING)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    verified_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_identity_documents'
        ordering = ['content_type', 'object_id', 'type']
        constraints = [
            models.UniqueConstraint(
                fields=['type', 'number_hash'], condition=models.Q(is_active=True) & ~models.Q(number_hash=''),
                name='uniq_active_identity_document_hash_per_type',
            ),
        ]

    def __str__(self):
        return f'{self.content_type_id}:{self.object_id} {self.type_id}'


class BankAccount(models.Model):
    ROUTING_IFSC = 'ifsc'
    ROUTING_IBAN = 'iban'
    ROUTING_SWIFT = 'swift_bic'
    ROUTING_SORT_CODE = 'sort_code'
    ROUTING_ABA = 'aba_routing'
    ROUTING_OTHER = 'other'
    ROUTING_CHOICES = [
        (ROUTING_IFSC, 'IFSC'), (ROUTING_IBAN, 'IBAN'), (ROUTING_SWIFT, 'SWIFT/BIC'),
        (ROUTING_SORT_CODE, 'Sort code'), (ROUTING_ABA, 'ABA routing'), (ROUTING_OTHER, 'Other'),
    ]
    SPLIT_REMAINDER = 'remainder'
    SPLIT_PERCENTAGE = 'percentage'
    SPLIT_FIXED = 'fixed'
    SPLIT_CHOICES = [(SPLIT_REMAINDER, 'Remainder'), (SPLIT_PERCENTAGE, 'Percentage'), (SPLIT_FIXED, 'Fixed amount')]
    STATUS_ACTIVE = 'active'
    STATUS_PENDING_APPROVAL = 'pending_approval'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [(STATUS_ACTIVE, 'Active'), (STATUS_PENDING_APPROVAL, 'Pending approval'), (STATUS_INACTIVE, 'Inactive')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bank_accounts')
    country = models.ForeignKey('platform_core.Country', on_delete=models.PROTECT, related_name='+')
    bank_name = models.CharField(max_length=150, blank=True)
    branch_name = models.CharField(max_length=150, blank=True)

    account_number = EncryptedCharField(max_length=500, blank=True)
    account_number_hash = models.CharField(max_length=64, blank=True, db_index=True)
    routing_code_type = models.CharField(max_length=20, choices=ROUTING_CHOICES, default=ROUTING_IFSC)
    routing_code = EncryptedCharField(max_length=500, blank=True)
    account_holder_name = models.CharField(max_length=150, blank=True)
    account_type = models.CharField(max_length=30, blank=True)
    currency = models.ForeignKey('platform_core.Currency', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    is_primary = models.BooleanField(default=False)
    split_type = models.CharField(max_length=20, choices=SPLIT_CHOICES, default=SPLIT_REMAINDER)
    split_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    priority = models.PositiveSmallIntegerField(default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_bank_accounts_v2'
        ordering = ['employee', '-is_primary', 'priority']

    def __str__(self):
        return f'{self.employee_id}:{self.bank_name} ({self.status})'
