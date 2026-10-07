"""
Phase 3A Task D — the policy engine: versioned, effective-dated business
parameters assigned to employees by various targeting strategies, resolved
through services_policies.resolve(). No runtime DDL — PolicyType declares
a JSON Schema; Policy.parameters is validated against it, never a new
table per policy type.
"""
from __future__ import annotations

import uuid

from django.contrib.postgres.fields import DateRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.db.models import CheckConstraint, F, Func, Q, Value
from django.db.models.functions import Coalesce

# A fixed, never-real sentinel UUID standing in for "global / no legal
# entity" inside the exclusion constraint below. Postgres EXCLUDE
# constraints treat NULL <> NULL (not equal, per standard NULL semantics),
# so two "global default" policies (legal_entity=NULL) would NOT be
# caught as overlapping without this — wrapping the column in
# Coalesce(..., SENTINEL) makes two NULLs compare equal for the
# constraint's purposes without needing legal_entity itself to be
# NOT NULL (which would lose the real "null = all legal entities"
# meaning everywhere else it's read).
_GLOBAL_LEGAL_ENTITY_SENTINEL = uuid.UUID('00000000-0000-0000-0000-000000000000')

from apps.accounts.migration_utils import PortableExclusionConstraint as ExclusionConstraint

from .phase1 import LegalEntity, TimestampedModel

# Task D.3's default specificity order — configuration, not code, but a
# real default has to live somewhere; PolicyType.specificity_order
# defaults to this list (most-specific first) and can be overridden.
DEFAULT_SPECIFICITY_ORDER = [
    'individual', 'position', 'org_unit', 'designation', 'grade',
    'employment_type', 'location', 'legal_entity', 'default',
]


class PolicyType(TimestampedModel):
    STRATEGY_SINGLE = 'single'
    STRATEGY_MERGE = 'merge'
    STRATEGY_CHOICES = [(STRATEGY_SINGLE, 'Single winner'), (STRATEGY_MERGE, 'Field-level merge')]

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    module = models.CharField(max_length=50, blank=True)
    parameter_schema = models.JSONField(default=dict, blank=True, help_text='JSON Schema for Policy.parameters.')
    resolution_strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES, default=STRATEGY_SINGLE)
    specificity_order = models.JSONField(default=list, blank=True, help_text='Most-specific target_type first; empty = DEFAULT_SPECIFICITY_ORDER.')
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_policy_types'
        ordering = ['code']

    def __str__(self):
        return self.code

    def get_specificity_order(self) -> list[str]:
        return self.specificity_order or DEFAULT_SPECIFICITY_ORDER


class Policy(TimestampedModel):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_RETIRED = 'retired'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_PUBLISHED, 'Published'), (STATUS_RETIRED, 'Retired')]

    type = models.ForeignKey(PolicyType, on_delete=models.PROTECT, related_name='policies')
    code = models.CharField(max_length=100, help_text='Unique per type.')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    parameters = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', help_text='Null = all legal entities.')
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_policies'
        ordering = ['type', 'code', '-effective_from']
        constraints = [
            CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F('effective_from')),
                name='policy_effective_to_gte_from',
                violation_error_message='The end date cannot be before the start date.',
            ),
            # Only one DEFAULT policy per (type, legal_entity) active at any
            # given date — Task D.2's "only one default per type per legal
            # entity at any date" rule, enforced at the DB level exactly
            # like Placement's no-overlap constraints.
            ExclusionConstraint(
                name='policy_one_default_per_type_entity_no_overlap',
                condition=Q(is_default=True),
                violation_error_message='Another default policy of this type already covers an overlapping date range for this legal entity.',
                expressions=[
                    ('type', RangeOperators.EQUAL),
                    (
                        Coalesce('legal_entity_id', Value(_GLOBAL_LEGAL_ENTITY_SENTINEL)),
                        RangeOperators.EQUAL,
                    ),
                    (
                        Func(
                            'effective_from', 'effective_to',
                            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
                            function='daterange', output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def __str__(self):
        return f'{self.type_id}:{self.code} v{self.version}'


class PolicyAssignment(TimestampedModel):
    TARGET_INDIVIDUAL = 'individual'
    TARGET_POSITION = 'position'
    TARGET_ORG_UNIT = 'org_unit'
    TARGET_DESIGNATION = 'designation'
    TARGET_GRADE = 'grade'
    TARGET_EMPLOYMENT_TYPE = 'employment_type'
    TARGET_LOCATION = 'location'
    TARGET_LEGAL_ENTITY = 'legal_entity'
    TARGET_EMPLOYEE_GROUP = 'employee_group'
    TARGET_CHOICES = [
        (TARGET_INDIVIDUAL, 'Individual employee'), (TARGET_POSITION, 'Position'),
        (TARGET_ORG_UNIT, 'Org unit'), (TARGET_DESIGNATION, 'Designation'), (TARGET_GRADE, 'Grade'),
        (TARGET_EMPLOYMENT_TYPE, 'Employment type'), (TARGET_LOCATION, 'Location/branch'),
        (TARGET_LEGAL_ENTITY, 'Legal entity'), (TARGET_EMPLOYEE_GROUP, 'Employee group (saved filter)'),
    ]

    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='assignments')
    # Denormalized from policy.type — an ExclusionConstraint's expressions
    # can only reference real columns on THIS table, never a joined field
    # like "policy__type", so the type is copied here at save() time
    # rather than looked up through the FK for the constraint to use.
    policy_type = models.ForeignKey(PolicyType, on_delete=models.CASCADE, related_name='+', editable=False)
    target_type = models.CharField(max_length=30, choices=TARGET_CHOICES)
    # A target may be identified by a real FK id (position/org_unit/
    # employee/legal_entity pk) or a plain code (designation/grade/
    # employment_type/location) — one generic field covers both rather
    # than a different column per target_type.
    target_id = models.CharField(max_length=64, blank=True)
    include_children = models.BooleanField(default=False, help_text='org_unit only — also matches descendant org units.')

    condition = models.JSONField(default=dict, blank=True, help_text='Optional rule expression (services_rules format).')
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'platform_policy_assignments'
        ordering = ['policy', '-effective_from']
        constraints = [
            CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F('effective_from')),
                name='policy_assignment_effective_to_gte_from',
                violation_error_message='The end date cannot be before the start date.',
            ),
            ExclusionConstraint(
                name='policy_assignment_no_overlap_same_target',
                violation_error_message='This target already has an overlapping assignment of this policy type.',
                expressions=[
                    ('target_type', RangeOperators.EQUAL),
                    ('target_id', RangeOperators.EQUAL),
                    ('policy_type', RangeOperators.EQUAL),
                    (
                        Func(
                            'effective_from', 'effective_to',
                            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
                            function='daterange', output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def __str__(self):
        return f'{self.policy_id} -> {self.target_type}:{self.target_id}'

    def save(self, *args, **kwargs):
        self.policy_type_id = self.policy.type_id
        super().save(*args, **kwargs)
