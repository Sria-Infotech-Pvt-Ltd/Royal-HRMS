"""
Phase 7A Task C — pay structures and the formula graph.

`PayStructure` groups `PayComponent` codes (Task B) into an ordered,
versioned template with a balancing component and a CTC definition.
`services_pay_structure.py` builds the dependency graph between a
structure's components (who references whose code as a base), rejects
cycles, computes in topological order, and runs the publish-time preview.

Still not wired into the live engine — `apps.payroll.engine.legacy` is
untouched. This is the second data-model layer Task E (payslip lines) and
a future real engine will consume.
"""
import uuid

from django.db import models


class PayStructure(models.Model):
    STATUS_DRAFT     = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_RETIRED   = 'retired'
    STATUS_CHOICES = [
        (STATUS_DRAFT,     'Draft'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_RETIRED,   'Retired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    legal_entity = models.ForeignKey(
        'platform_core.LegalEntity', on_delete=models.PROTECT, null=True, blank=True,
        related_name='pay_structures',
        help_text='Blank = applies across every legal entity (matches today\'s single-entity reality).',
    )
    currency = models.ForeignKey(
        'platform_core.Currency', on_delete=models.PROTECT, null=True, blank=True,
        related_name='pay_structures',
    )
    balancing_component_code = models.CharField(
        max_length=40, blank=True,
        help_text='Component code computed as CTC minus every other component (e.g. SPECIAL). Blank = no balancing component.',
    )
    ctc_definition_codes = models.JSONField(
        default=list, blank=True,
        help_text='Component codes that count towards CTC (earnings + employer contributions this structure includes). Empty list = every earning component by convention.',
    )
    version = models.PositiveIntegerField(default=1)
    effective_from = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_pay_structures_v2'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} v{self.version}'


class PayStructureComponent(models.Model):
    """One component's row within a structure — references PayComponent by
    `code` (not FK: a structure-level override of calculation_method/value
    shouldn't require touching the shared master row, and a formula may
    reference an aggregate code that isn't a real PayComponent at all, e.g.
    GROSS_FOR_PF)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    structure = models.ForeignKey(PayStructure, on_delete=models.CASCADE, related_name='structure_components')
    component_code = models.CharField(max_length=40)

    # Override of the component's own calculation_method/base/value for THIS
    # structure only — blank fields fall back to the PayComponent master row.
    calculation_method = models.CharField(max_length=20, blank=True)
    base_component_code = models.CharField(max_length=40, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    # A formula is a small expression referencing other component codes in
    # this same structure by name, e.g. "BASIC * 0.5" or "GROSS - PF_EE" —
    # evaluated by services_pay_structure.evaluate_structure() after
    # topological sort. No code execution: parsed and evaluated through
    # Python's own `ast` module restricted to Name/Num/BinOp/arithmetic
    # operators only (see services_pay_structure._SAFE_NODES) — never
    # `eval()` on raw untrusted input.
    formula = models.TextField(blank=True)

    mandatory = models.BooleanField(default=True)
    editable_per_employee = models.BooleanField(default=False)
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'payroll_pay_structure_components_v2'
        unique_together = [('structure', 'component_code')]
        ordering = ['order']

    def __str__(self):
        return f'{self.structure.code} › {self.component_code}'
