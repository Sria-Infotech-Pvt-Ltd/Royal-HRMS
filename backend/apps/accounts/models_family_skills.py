
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class EmergencyContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='emergency_contacts')
    name = models.CharField(max_length=150)
    relationship = models.ForeignKey('platform_core.LookupValue', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    priority = models.PositiveSmallIntegerField(default=0)
    family_member = models.ForeignKey('FamilyMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_emergency_contacts'
        ordering = ['employee', 'priority']

    def __str__(self):
        return f'{self.employee_id}:{self.name}'


class Nomination(models.Model):
    """Generalises EPFNominee (Task F.4) — kept, not replaced; NOT
    migrated in this pass (Task L deferred)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='nominations_v2')
    scheme = models.ForeignKey('platform_core.LookupValue', on_delete=models.PROTECT, related_name='+', help_text='Country-pack lookup: PF, EPS, gratuity, group insurance, etc.')
    family_member = models.ForeignKey('FamilyMember', on_delete=models.CASCADE, related_name='nominations_v2')
    share_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    guardian = models.ForeignKey('FamilyMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', help_text='Required for a minor nominee, if the scheme requires it.')
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_nominations'
        ordering = ['employee', 'scheme']

    def __str__(self):
        return f'{self.employee_id}:{self.scheme_id}:{self.family_member_id}'


class SkillMaster(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_skill_masters'
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class EmployeeSkill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skills')
    skill = models.ForeignKey(SkillMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    skill_text = models.CharField(max_length=150, blank=True, help_text='Freeform fallback when no SkillMaster row matched during the text-split migration.')
    proficiency = models.ForeignKey('platform_core.LookupValue', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    years = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    last_used = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_skills'
        ordering = ['employee', '-is_primary']

    def __str__(self):
        return f'{self.employee_id}:{self.skill_id or self.skill_text}'


class EmployeeCertification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='certifications_v2')
    name = models.CharField(max_length=200)
    issuer = models.CharField(max_length=200, blank=True)
    credential_id = models.CharField(max_length=100, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    verification_status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_certifications'
        ordering = ['employee', '-issue_date']

    def __str__(self):
        return f'{self.employee_id}:{self.name}'


class EmployeeLanguage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='languages')
    language_code = models.CharField(max_length=10, help_text='ISO 639-1, e.g. "en", "hi".')
    can_read = models.BooleanField(default=False)
    can_write = models.BooleanField(default=False)
    can_speak = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_employee_languages'
        ordering = ['employee', 'language_code']
        constraints = [models.UniqueConstraint(fields=['employee', 'language_code'], name='uniq_employee_language')]

    def __str__(self):
        return f'{self.employee_id}:{self.language_code}'


class StatutoryEnrolment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='statutory_enrolments')
    scheme = models.ForeignKey('platform_core.LookupValue', on_delete=models.PROTECT, related_name='+', help_text='Country-pack lookup: PF, ESI, PT, LWF, NPS, etc.')
    is_enrolled = models.BooleanField(default=True)
    identity_document = models.ForeignKey('IdentityDocument', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    opt_out_reason = models.CharField(max_length=255, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_statutory_enrolments'
        ordering = ['employee', 'scheme']

    def __str__(self):
        return f'{self.employee_id}:{self.scheme_id} ({"enrolled" if self.is_enrolled else "opted out"})'
