"""
Phase 4 — the new authorization engine's own models. Built additively
alongside the existing Role/Permission/RolePermission/User.role system
(apps.accounts), which stays the live source of truth while flag
`authz.v2` is OFF (default). See PHASE4_REPORT.md for what is/isn't
wired to actually replace the old system in this pass.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, F, Q

from .fields import EntityDefinition
from .phase1 import LegalEntity, TimestampedModel


class RoleAssignment(TimestampedModel):
    """Task B.1 — a user may hold many of these; effective rights are
    the union (subject to SoD, Task F). `User.role` (apps.accounts)
    stays the single "primary role" for backward compatibility and is
    kept in sync with the user's primary assignment while the flag is
    OFF — see services_authz.py's sync helper."""
    SCOPE_OWN = 'own'
    SCOPE_DIRECT_REPORTS = 'direct_reports'
    SCOPE_ALL_REPORTS = 'all_reports'
    SCOPE_DOTTED_LINE_REPORTS = 'dotted_line_reports'
    SCOPE_ORG_UNIT = 'org_unit'
    SCOPE_MY_ORG_UNIT = 'my_org_unit'
    SCOPE_BRANCH = 'branch'
    SCOPE_MY_BRANCHES = 'my_branches'
    SCOPE_LEGAL_ENTITY = 'legal_entity'
    SCOPE_MY_LEGAL_ENTITY = 'my_legal_entity'
    SCOPE_EMPLOYEE_GROUP = 'employee_group'
    SCOPE_ALL = 'all'
    SCOPE_CHOICES = [
        (SCOPE_OWN, 'Own records only'), (SCOPE_DIRECT_REPORTS, 'Direct reports'),
        (SCOPE_ALL_REPORTS, 'Full reporting tree'), (SCOPE_DOTTED_LINE_REPORTS, 'Dotted-line reports'),
        (SCOPE_ORG_UNIT, 'Selected org units'), (SCOPE_MY_ORG_UNIT, 'My org unit (+children)'),
        (SCOPE_BRANCH, 'Selected branches'), (SCOPE_MY_BRANCHES, 'My branches'),
        (SCOPE_LEGAL_ENTITY, 'Selected legal entities'), (SCOPE_MY_LEGAL_ENTITY, 'My legal entity'),
        (SCOPE_EMPLOYEE_GROUP, 'Employee group (saved filter)'), (SCOPE_ALL, 'Everything'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey('accounts.Role', on_delete=models.CASCADE, related_name='assignments')

    scope_type = models.CharField(max_length=30, choices=SCOPE_CHOICES, default=SCOPE_OWN)
    scope_values = models.JSONField(default=list, blank=True, help_text='ids/codes for org_unit/branch/legal_entity/employee_group scope types; ignored for the rest.')
    include_children = models.BooleanField(default=False, help_text='org_unit/my_org_unit only — also matches descendant org units.')

    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', help_text='Null = every legal entity the user is otherwise entitled to.')
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reason = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True, help_text='Flipped False by the expiry job (Phase 3B scheduler) once effective_to passes, rather than deleted — history is kept.')

    class Meta:
        db_table = 'platform_role_assignments'
        ordering = ['user', '-effective_from']
        constraints = [
            CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F('effective_from')),
                name='role_assignment_effective_to_gte_from',
                violation_error_message='The end date cannot be before the start date.',
            ),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.role_id}:{self.scope_type}'


class FieldPermission(TimestampedModel):
    """Task E.1."""
    ACCESS_HIDDEN = 'hidden'
    ACCESS_MASKED = 'masked'
    ACCESS_READ = 'read'
    ACCESS_EDIT = 'edit'
    ACCESS_CHOICES = [
        (ACCESS_HIDDEN, 'Hidden'), (ACCESS_MASKED, 'Masked'), (ACCESS_READ, 'Read'), (ACCESS_EDIT, 'Edit'),
    ]

    role = models.ForeignKey('accounts.Role', on_delete=models.CASCADE, related_name='field_permissions')
    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name='field_permissions')
    field_code = models.CharField(max_length=64, help_text='A Phase 2 FieldDefinition.code for a custom field, or a core model field name.')
    access = models.CharField(max_length=10, choices=ACCESS_CHOICES, default=ACCESS_READ)
    condition = models.JSONField(default=dict, blank=True, help_text='Optional rule expression (services_rules format) narrowing when this access level applies.')
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'platform_field_permissions'
        ordering = ['role', 'entity', 'field_code']
        constraints = [
            models.UniqueConstraint(fields=['role', 'entity', 'field_code'], name='uniq_field_permission_per_role_entity_field'),
        ]

    def __str__(self):
        return f'{self.role_id}:{self.entity_id}:{self.field_code} = {self.access}'


class SensitiveFieldReadLog(models.Model):
    """Task E.5 — audit WHO viewed an unmasked sensitive field value,
    WHEN, on WHICH record, WHICH field — never the value itself (Rule 6)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    entity = models.ForeignKey(EntityDefinition, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    object_id = models.CharField(max_length=64)
    field_code = models.CharField(max_length=64)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_sensitive_field_read_logs'
        ordering = ['-occurred_at']
        indexes = [models.Index(fields=['entity', 'object_id', 'occurred_at'], name='psfrl_record_time_idx')]

    def __str__(self):
        return f'{self.user_id} read {self.entity_id}:{self.object_id}.{self.field_code}'


class SoDRule(TimestampedModel):
    """Task F.1. `conflicting_permissions_a`/`b`: holding ANY of A plus
    ANY of B is a conflict."""
    SEVERITY_BLOCK = 'block'
    SEVERITY_WARN = 'warn'
    SEVERITY_CHOICES = [(SEVERITY_BLOCK, 'Block'), (SEVERITY_WARN, 'Warn')]

    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    conflicting_permissions_a = models.JSONField(default=list, help_text='List of permission codenames (set A).')
    conflicting_permissions_b = models.JSONField(default=list, help_text='List of permission codenames (set B).')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default=SEVERITY_WARN)
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_suggestion = models.BooleanField(default=True, help_text='Task F.3 — seeded rules start as suggestions pending owner confirmation, not auto-enforced truth.')
    is_active = models.BooleanField(default=False, help_text='A suggestion only actually blocks/warns once an owner activates it.')

    class Meta:
        db_table = 'platform_sod_rules'
        ordering = ['code']

    def __str__(self):
        return self.code


class SoDViolationLog(models.Model):
    """Task F.4 — a record of a conflict found, either at grant time
    (blocked) or pre-existing (reported, never auto-removed)."""
    rule = models.ForeignKey(SoDRule, on_delete=models.CASCADE, related_name='violations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    detected_at = models.DateTimeField(auto_now_add=True)
    was_blocked = models.BooleanField(default=False)
    reason = models.CharField(max_length=255, blank=True, help_text='Mandatory for a warn-severity violation that proceeded anyway.')

    class Meta:
        db_table = 'platform_sod_violation_logs'
        ordering = ['-detected_at']

    def __str__(self):
        return f'{self.rule_id}:{self.user_id} ({"blocked" if self.was_blocked else "warned"})'
