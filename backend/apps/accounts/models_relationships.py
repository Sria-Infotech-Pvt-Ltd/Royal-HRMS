"""
Phase 5B Task B — effective-dated employee relationships (reporting
manager, HR partner, approver, dotted-line manager, mentor, buddy...),
admin-extensible via a LookupType rather than a fixed choices= list.

Additive only: `User.reporting_manager`/`hr`/`reporting_approver`/
`dotted_line_manager` stay the live FK columns read by every existing
call site in this phase — nothing here replaces them yet. They become
caches of "the relationship effective today" only once Task L's cutover
runs (see PHASE5B_REPORT.md). Building this model now, standalone and
tested, is what lets that future cutover exist at all.
"""
from __future__ import annotations

import uuid

from django.db import models


class EmployeeRelationship(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='relationships_v2')
    relationship_type = models.ForeignKey(
        'platform_core.LookupValue', on_delete=models.PROTECT, related_name='employee_relationships',
        limit_choices_to={'lookup_type__code': 'EMPLOYEE_RELATIONSHIP_TYPE'},
    )
    related_employee = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='related_to_relationships_v2',
    )
    SOURCE_MANUAL = 'manual'
    SOURCE_DERIVED = 'derived'
    SOURCE_CHOICES = [(SOURCE_MANUAL, 'Manual'), (SOURCE_DERIVED, 'Derived from org chart')]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_relationships'
        ordering = ['-effective_from']
        indexes = [
            models.Index(fields=['employee', 'relationship_type', 'effective_from']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F('effective_from')),
                name='employee_relationship_effective_to_gte_from',
            ),
        ]

    def __str__(self):
        return f'{self.employee_id} --{self.relationship_type_id}--> {self.related_employee_id}'
