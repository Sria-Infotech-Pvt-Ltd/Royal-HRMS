"""
Phase 3A Task C — rule definitions, test cases, versions, and slab/band
tables. The expression TREE itself (JSON, whitelisted-node format) is
documented in docs/RULES.md and evaluated by services_rules.py — this
file only stores it, never executes it.
"""
from __future__ import annotations

from django.contrib.postgres.fields import DateRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.db.models import CheckConstraint, F, Func, Q

from apps.accounts.migration_utils import PortableExclusionConstraint as ExclusionConstraint

from .phase1 import LegalEntity, TimestampedModel


class RuleDefinition(TimestampedModel):
    PURPOSE_CONDITION = 'condition'
    PURPOSE_CALCULATION = 'calculation'
    PURPOSE_VALIDATION = 'validation'
    PURPOSE_ELIGIBILITY = 'eligibility'
    PURPOSE_DEFAULT_VALUE = 'default_value'
    PURPOSE_APPROVER_SELECTION = 'approver_selection'
    PURPOSE_OTHER = 'other'
    PURPOSE_CHOICES = [
        (PURPOSE_CONDITION, 'Condition'), (PURPOSE_CALCULATION, 'Calculation'),
        (PURPOSE_VALIDATION, 'Validation'), (PURPOSE_ELIGIBILITY, 'Eligibility'),
        (PURPOSE_DEFAULT_VALUE, 'Default value'), (PURPOSE_APPROVER_SELECTION, 'Approver selection'),
        (PURPOSE_OTHER, 'Other'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_RETIRED = 'retired'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_PUBLISHED, 'Published'), (STATUS_RETIRED, 'Retired')]

    RETURN_TYPE_CHOICES = [
        ('number', 'Number'), ('integer', 'Integer'), ('string', 'String'), ('boolean', 'Boolean'),
        ('date', 'Date'), ('datetime', 'Date & time'), ('time', 'Time'), ('duration', 'Duration'),
        ('lookup_code', 'Lookup code'), ('list', 'List'), ('null', 'Null'),
    ]

    code = models.CharField(max_length=100, unique=True, help_text='Immutable after first publish.')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    module = models.CharField(max_length=50, blank=True)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default=PURPOSE_CONDITION)

    # {"variable_name": {"type": "number"|...}} — the evaluator's static
    # type-checker validates the expression tree against exactly this,
    # never against live data.
    input_context = models.JSONField(default=dict, blank=True)
    return_type = models.CharField(max_length=20, choices=RETURN_TYPE_CHOICES, default='boolean')
    expression = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    version = models.PositiveIntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'platform_rule_definitions'
        ordering = ['module', 'code']

    def __str__(self):
        return self.code


class RuleVersion(models.Model):
    """Immutable snapshot created on every publish — Task C.3's
    version-by-effective-date requirement. Consumers resolve a rule by
    (code, as_of) through services_rules.get_effective_version(), never
    by reading RuleDefinition.expression directly for anything but
    draft editing/testing."""
    rule = models.ForeignKey(RuleDefinition, on_delete=models.CASCADE, related_name='versions')
    version = models.PositiveIntegerField()
    expression = models.JSONField()
    input_context = models.JSONField()
    return_type = models.CharField(max_length=20)
    effective_from = models.DateField()
    published_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'platform_rule_versions'
        ordering = ['rule', '-effective_from']
        constraints = [
            models.UniqueConstraint(fields=['rule', 'version'], name='uniq_rule_version'),
        ]

    def __str__(self):
        return f'{self.rule_id} v{self.version}'


class RuleTestCase(TimestampedModel):
    """Task C.2 — a rule cannot publish unless it has >=1 test case and
    all pass. `inputs` must be synthetic (Rule 6 — never real personal
    data); nothing here enforces that mechanically, it's a process rule
    documented in docs/RULES.md."""
    rule = models.ForeignKey(RuleDefinition, on_delete=models.CASCADE, related_name='test_cases')
    name = models.CharField(max_length=150)
    inputs = models.JSONField(default=dict, blank=True)
    expected_output = models.JSONField(null=True, blank=True)
    last_result = models.JSONField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)

    class Meta:
        db_table = 'platform_rule_test_cases'
        ordering = ['rule', 'name']

    def __str__(self):
        return f'{self.rule_id}:{self.name}'


class RuleTable(TimestampedModel):
    """Task C.4 — slab/band data for services_rules.slab()/band()."""
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    columns = models.JSONField(default=list, help_text='[{"name": "min", "type": "number"}, ...]')

    class Meta:
        db_table = 'platform_rule_tables'
        ordering = ['code']

    def __str__(self):
        return self.code


class RuleTableVersion(models.Model):
    table = models.ForeignKey(RuleTable, on_delete=models.CASCADE, related_name='versions')
    rows = models.JSONField(default=list, help_text='List of row dicts matching RuleTable.columns.')
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    country = models.ForeignKey('platform_core.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'platform_rule_table_versions'
        ordering = ['table', '-effective_from']
        constraints = [
            CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F('effective_from')),
                name='rule_table_version_effective_to_gte_from',
                violation_error_message='The end date cannot be before the start date.',
            ),
            ExclusionConstraint(
                name='rule_table_version_no_overlap',
                violation_error_message='This table already has an overlapping version for that date range.',
                expressions=[
                    ('table', RangeOperators.EQUAL),
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
        return f'{self.table_id} ({self.effective_from} – {self.effective_to or "present"})'
