"""
Phase 9A Task A/B/C — the report builder, execution/export audit, and
dashboards. Scoped down, stated plainly: this engine queries ONLY
`CustomRecord` rows (Phase 2's one real table for every custom entity) —
not an arbitrary join graph across every core Django model in this
codebase. A `base_entity` must be a `kind=custom` EntityDefinition.
Reporting on CORE entities (User/EmployeePayslip/etc.) through this same
builder is real, separate work (each core model needs its own safe
column-path whitelist); every existing core report/export endpoint keeps
working completely unchanged, catalogued as "not migrated" in the Phase
9A report rather than silently assumed covered.

No arbitrary joins, no raw SQL, no calculated-column code execution —
`services_report_builder.py`'s expression evaluator is the same
`ast`-restricted sandbox pattern already proven in Phase 7A
(services_pay_structure.py's formula evaluator), reused here rather than
reinvented.
"""
import uuid

from django.db import models


class ReportDefinition(models.Model):
    VISIBILITY_PERSONAL  = 'personal'
    VISIBILITY_POSITIONS = 'positions'
    VISIBILITY_EVERYONE  = 'everyone'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PERSONAL, 'Personal'), (VISIBILITY_POSITIONS, 'Specific positions'), (VISIBILITY_EVERYONE, 'Everyone with access'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    base_entity = models.ForeignKey('platform_core.EntityDefinition', on_delete=models.PROTECT, related_name='report_definitions')
    owner = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='report_definitions_owned')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_PERSONAL)
    shared_position_titles = models.JSONField(default=list, blank=True, help_text='Position titles this report is shared to, when visibility=positions.')

    # [{"field_code": "amount", "label": "Amount"}, ...] — field_code must
    # exist on base_entity's FieldDefinition set; validated at save time.
    columns = models.JSONField(default=list)
    # [{"name": "total_cost", "expression": "base_salary + bonus", "label": "Total Cost"}]
    # — expression is restricted arithmetic over OTHER declared column names only.
    calculated_columns = models.JSONField(default=list, blank=True)
    # [{"field_code": "status", "operator": "eq", "value": "...", "prompted": false}]
    filters = models.JSONField(default=list, blank=True)
    group_by_field_codes = models.JSONField(default=list, blank=True)
    # [{"field_code": "amount", "function": "sum"}] — count/sum/avg/min/max/distinct_count.
    aggregates = models.JSONField(default=list, blank=True)
    sort = models.JSONField(default=list, blank=True, help_text='[{"field_code": "...", "direction": "asc"}]')
    row_limit = models.PositiveIntegerField(default=10000)
    chart_type = models.CharField(max_length=20, choices=[('table', 'Table'), ('bar', 'Bar'), ('line', 'Line'), ('pie', 'Pie')], default='table')

    # Below this group size, an aggregate over a sensitive field is
    # suppressed (inference-attack protection, Task A's own explicit
    # testing requirement) rather than silently shown.
    min_group_size_for_sensitive_aggregate = models.PositiveSmallIntegerField(default=5)

    version = models.PositiveIntegerField(default=1)
    is_system = models.BooleanField(default=False, help_text='Seeded standard report — still editable, never silently overwritten by a re-seed (update_or_create on code only touches fields the seed owns).')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_report_definitions_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class ReportRun(models.Model):
    """Audit row per execution — who, what report, parameters, ROW COUNT
    only, never the actual result rows (Task B.2's own 'no data' rule for
    export audits, applied here to every run too)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(ReportDefinition, on_delete=models.CASCADE, related_name='runs')
    run_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='report_runs')
    parameters = models.JSONField(default=dict, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    export_format = models.CharField(max_length=10, blank=True, choices=[('csv', 'CSV'), ('xlsx', 'XLSX'), ('pdf', 'PDF')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_report_runs_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.report_id} by {self.run_by_id} ({self.row_count} rows)'


class Dashboard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=150)
    position_title = models.CharField(max_length=150, blank=True, help_text='Blank = personal dashboard (see owner); set = the default for people in this position.')
    owner = models.ForeignKey('accounts.User', on_delete=models.CASCADE, null=True, blank=True, related_name='personal_dashboards')
    layout = models.JSONField(default=list, help_text='[{"widget_id": "...", "x": 0, "y": 0, "w": 4, "h": 2}, ...]')

    class Meta:
        db_table = 'platform_dashboards_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class Widget(models.Model):
    TYPE_KPI   = 'kpi'
    TYPE_CHART = 'chart'
    TYPE_TABLE = 'table'
    TYPE_CHOICES = [(TYPE_KPI, 'KPI'), (TYPE_CHART, 'Chart'), (TYPE_TABLE, 'Table')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name='widgets')
    widget_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_TABLE)
    report = models.ForeignKey(ReportDefinition, on_delete=models.CASCADE, null=True, blank=True, related_name='widgets')
    report_parameters = models.JSONField(default=dict, blank=True)
    title = models.CharField(max_length=150, blank=True)
    refresh_interval_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'platform_widgets_v2'
        ordering = ['dashboard']

    def __str__(self):
        return f'{self.dashboard_id}: {self.title or self.widget_type}'
