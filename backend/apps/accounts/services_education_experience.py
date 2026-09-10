"""
Keeps EmployeeProfile's legacy flat Education/Experience fields
(highest_qualification/institution/specialization/year_of_passing,
previous_employer/previous_designation/leaving_reason) mirroring the new
EducationRecord/WorkExperienceRecord tables — the same "richer source of
truth syncs a simpler legacy field" pattern services_placement.py already
uses to keep User.designation/department in sync from Position.

Three UI surfaces (Employee Detail's own Edit Employee tab, My Profile, the
candidate-review Onboarding Drawer) were never rebuilt to read the new
tables directly — this keeps them showing a correct, if summarized, value
with zero changes to any of them, at the cost of Employee Detail's own
Education tab being effectively read-only in practice (an edit made there
gets overwritten the next time this sync runs).
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import User


def _compute_total_experience_years(records: list) -> 'Decimal | None':
    """Sum of WorkExperienceRecord durations, merging overlapping/adjacent
    date ranges so concurrent jobs are never double-counted (rare, but a
    real possibility — two part-time roles at once, say). An entry missing
    a start_date, or with an end_date before its start_date, contributes
    nothing (there's no valid range to measure). "Currently working here"
    (end_date=None) counts through today. Returns None if there's nothing
    to compute from — a fresher with no entries, or entries with no usable
    dates yet."""
    today = date.today()
    intervals = []
    for r in records:
        if not r.start_date:
            continue
        end = r.end_date or today
        if end < r.start_date:
            continue
        intervals.append((r.start_date, end))
    if not intervals:
        return None

    intervals.sort(key=lambda iv: iv[0])
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    total_days = sum((end - start).days for start, end in merged)
    return (Decimal(total_days) / Decimal('365.25')).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


def sync_legacy_education_experience_fields(employee: 'User') -> None:
    from apps.accounts.models import EDUCATION_LEVEL_RANK, EducationRecord, EmployeeProfile, WorkExperienceRecord

    # get_or_create, not a bare lookup — Education/Experience can be the
    # very first onboarding data saved for a brand-new employee, before any
    # other step has created their EmployeeProfile row yet (every other
    # onboarding call site follows this same get_or_create convention).
    profile, _ = EmployeeProfile.objects.get_or_create(user=employee)

    update_fields = []

    # level is no longer unique per employee (two Bachelor's degrees, or two
    # "Other" entries, are both valid now) — records already come back in
    # the model's own ordering (['order', '-end_date']), so the first match
    # for a given level is that level's most recent/most-complete entry.
    records = list(EducationRecord.objects.filter(employee=employee))

    def best_for_level(level: str):
        return next((r for r in records if r.level == level and r.has_any_data()), None)

    highest = next(
        (best_for_level(level) for level in EDUCATION_LEVEL_RANK if best_for_level(level)),
        None,
    )
    new_qualification = highest.display_label() if highest else ''
    new_institution    = highest.institution      if highest else ''
    new_specialization = highest.specialization   if highest else ''
    if highest and (highest.end_date or highest.start_date):
        new_year = (highest.end_date or highest.start_date).year
    else:
        new_year = None
    if (
        profile.highest_qualification != new_qualification or profile.institution != new_institution
        or profile.specialization != new_specialization or profile.year_of_passing != new_year
    ):
        profile.highest_qualification = new_qualification
        profile.institution = new_institution
        profile.specialization = new_specialization
        profile.year_of_passing = new_year
        update_fields += ['highest_qualification', 'institution', 'specialization', 'year_of_passing']

    experience_records = list(WorkExperienceRecord.objects.filter(employee=employee))

    # Prefer whichever experience row has no end_date (still ongoing at the
    # time it was recorded); otherwise the most recently-started one.
    current_or_latest = (
        next((r for r in experience_records if r.end_date is None), None)
        or max(experience_records, key=lambda r: r.start_date or date.min, default=None)
    )
    new_employer    = current_or_latest.employer_name      if current_or_latest else ''
    new_designation = current_or_latest.designation        if current_or_latest else ''
    new_reason      = current_or_latest.reason_for_leaving if current_or_latest else ''
    if (
        profile.previous_employer != new_employer or profile.previous_designation != new_designation
        or profile.leaving_reason != new_reason
    ):
        profile.previous_employer = new_employer
        profile.previous_designation = new_designation
        profile.leaving_reason = new_reason
        update_fields += ['previous_employer', 'previous_designation', 'leaving_reason']

    # Total Experience (Years) — no longer a manually-entered field (see
    # views_education_experience.py's TotalExperienceView, GET-only now);
    # always derived from the entries themselves so it can never drift out
    # of sync with what's actually recorded.
    new_total_experience = _compute_total_experience_years(experience_records)
    if profile.total_experience_years != new_total_experience:
        profile.total_experience_years = new_total_experience
        update_fields.append('total_experience_years')

    if update_fields:
        profile.save(update_fields=[*update_fields, 'updated_at'])
