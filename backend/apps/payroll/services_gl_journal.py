"""
Phase 7B Task I — accounting journal. Entries are generated per finalised
run from PayslipLine amounts (Phase 7A Task E) via GLMapping, split by
cost centre — scoped down: cost centre comes from `employee.department`
(a plain string already on User) rather than a real Position-level cost
centre FK (no such field exists on this codebase's Position model today;
introducing one is out of this task's bounds), documented here rather than
silently assumed to be the master prompt's intended "cost centre."
Debits always equal credits — enforced by construction (every component
amount produces exactly one debit row and one credit row of the same
amount), not just asserted after the fact.
"""
from decimal import Decimal

from django.db import transaction

from apps.payroll.models import GLMapping, JournalEntry


@transaction.atomic
def generate_journal(run, payslips) -> list:
    """One JournalEntry PAIR (debit + credit) per (component_code, cost
    centre) combination actually present on `payslips`' PayslipLine rows.
    Idempotent — clears this run's own prior entries first."""
    JournalEntry.objects.filter(run=run, reversal_of__isnull=True).delete()

    totals = {}  # (component_code, cost_centre) -> Decimal
    for payslip in payslips:
        cost_centre = getattr(payslip.employee, 'department', '') or ''
        for line in payslip.lines.all():
            if line.amount == 0:
                continue
            key = (line.component_code, cost_centre)
            totals[key] = totals.get(key, Decimal('0')) + line.amount

    mappings = {m.component_code: m for m in GLMapping.objects.filter(is_active=True)}
    entries = []
    for (component_code, cost_centre), amount in totals.items():
        mapping = mappings.get(component_code)
        if mapping is None:
            continue  # unmapped component — reported separately by unmapped_components(), never guessed at
        narration = mapping.narration_template.format(
            component_code=component_code,
            period_start=run.period.period_start, period_end=run.period.period_end,
        )
        entries.append(JournalEntry.objects.create(
            run=run, account_code=mapping.debit_account_code, cost_centre=cost_centre,
            debit_amount=abs(amount), credit_amount=Decimal('0'), narration=narration,
        ))
        entries.append(JournalEntry.objects.create(
            run=run, account_code=mapping.credit_account_code, cost_centre=cost_centre,
            debit_amount=Decimal('0'), credit_amount=abs(amount), narration=narration,
        ))
    return entries


def unmapped_components(run, payslips) -> set:
    mapped_codes = set(GLMapping.objects.filter(is_active=True).values_list('component_code', flat=True))
    seen_codes = set()
    for payslip in payslips:
        seen_codes.update(payslip.lines.values_list('component_code', flat=True))
    return seen_codes - mapped_codes


def is_balanced(run) -> bool:
    from django.db.models import Sum
    totals = JournalEntry.objects.filter(run=run).aggregate(d=Sum('debit_amount'), c=Sum('credit_amount'))
    return (totals['d'] or Decimal('0')) == (totals['c'] or Decimal('0'))


@transaction.atomic
def reverse_journal(run, reversal_run) -> list:
    """Creates a mirror-image (debit<->credit swapped) JournalEntry per
    original entry, linked via reversal_of — the original is never edited."""
    reversed_entries = []
    for entry in JournalEntry.objects.filter(run=run, reversal_of__isnull=True):
        reversed_entries.append(JournalEntry.objects.create(
            run=reversal_run, reversal_of=entry, account_code=entry.account_code, cost_centre=entry.cost_centre,
            debit_amount=entry.credit_amount, credit_amount=entry.debit_amount,
            narration=f'Reversal of {entry.narration}',
        ))
    return reversed_entries
