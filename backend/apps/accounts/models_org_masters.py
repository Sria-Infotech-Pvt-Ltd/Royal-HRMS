"""
Phase 5A Task A — organisation masters (Grade, Band, JobFamily,
Designation, CostCenter). Additive: the existing text fields
(Position.grade, JobTemplate.band, OrgUnit.cost_center, User.designation)
are kept and kept in sync (Task A.2) — NOT executed in this pass, see
PHASE5A_REPORT.md. The `_ref` FK columns below exist and are usable
today; nothing yet reads them instead of the text columns.
"""
from __future__ import annotations

import uuid

from django.db import models


class Band(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    rank = models.PositiveSmallIntegerField(default=0, help_text='Ordering — lower rank is more junior.')
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_bands'
        ordering = ['rank', 'code']

    def __str__(self):
        return self.name


class Grade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    rank = models.PositiveSmallIntegerField(default=0)
    band = models.ForeignKey(Band, on_delete=models.SET_NULL, null=True, blank=True, related_name='grades')
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_grades'
        ordering = ['rank', 'code']

    def __str__(self):
        return self.name


class JobFamily(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_families')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_job_families'
        ordering = ['name']
        verbose_name_plural = 'job families'

    def __str__(self):
        return self.name


class Designation(models.Model):
    """Generalises the free-text designation strings scattered across
    User.designation/Position.title into a real master, without yet
    being the thing those columns read from (Task A.2 deferred)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    job_family = models.ForeignKey(JobFamily, on_delete=models.SET_NULL, null=True, blank=True, related_name='designations')
    default_grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_designations'
        ordering = ['name']

    def __str__(self):
        return self.name


class CostCenter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    owner = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_cost_centers'
        ordering = ['code']

    def __str__(self):
        return self.name
