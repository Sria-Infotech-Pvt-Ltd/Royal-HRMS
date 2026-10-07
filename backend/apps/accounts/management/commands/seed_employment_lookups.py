"""
Phase 5B Task A.1/A.2 — seeds the EMPLOYMENT_TYPE and EMPLOYMENT_STATUS
LookupTypes with behavior attributes, so logic can read
`attributes['probation_applicable']` etc. instead of comparing against
hardcoded strings. Additive only: `User.employee_type`/`employment_status`
stay the live CharField+choices source of truth in this phase — see
services_employment_lookups.py and PHASE5B_REPORT.md for why the actual
column cutover (Task A.3/A.4) is deferred to Task L.

Codes mirror the existing `User.EMPLOYMENT_TYPE_CHOICES` display strings
exactly (so `attributes['legacy_value']` round-trips the stored text
unchanged) and the seed EMPLOYMENT_STATUS list the Phase 5B prompt itself
specifies (Section 3, Task A.2).
"""
from django.core.management.base import BaseCommand

EMPLOYMENT_TYPES = [
    {'code': 'PERMANENT', 'legacy_value': 'Permanent', 'label': 'Permanent',
     'attrs': {'probation_applicable': True, 'pf_default_eligible': True, 'counts_in_headcount': True, 'is_temporary': False}},
    {'code': 'CONTRACT', 'legacy_value': 'Contract', 'label': 'Contract',
     'attrs': {'probation_applicable': False, 'pf_default_eligible': False, 'counts_in_headcount': True, 'is_temporary': True}},
    {'code': 'FREELANCER', 'legacy_value': 'Freelancer', 'label': 'Freelancer',
     'attrs': {'probation_applicable': False, 'pf_default_eligible': False, 'counts_in_headcount': False, 'is_temporary': True}},
    {'code': 'CONSULTANT', 'legacy_value': 'Consultant', 'label': 'Consultant',
     'attrs': {'probation_applicable': False, 'pf_default_eligible': False, 'counts_in_headcount': False, 'is_temporary': True}},
    {'code': 'PART_TIME', 'legacy_value': 'Part-Time', 'label': 'Part-Time',
     'attrs': {'probation_applicable': True, 'pf_default_eligible': True, 'counts_in_headcount': True, 'is_temporary': False}},
    {'code': 'TEMPORARY', 'legacy_value': 'Temporary', 'label': 'Temporary',
     'attrs': {'probation_applicable': False, 'pf_default_eligible': False, 'counts_in_headcount': True, 'is_temporary': True}},
    {'code': 'INTERN', 'legacy_value': 'Intern', 'label': 'Intern',
     'attrs': {'probation_applicable': False, 'pf_default_eligible': False, 'counts_in_headcount': False, 'is_temporary': True}},
]

RELATIONSHIP_TYPES = [
    {'code': 'REPORTING_MANAGER', 'label': 'Reporting Manager', 'derived_from_org_chart': True, 'allow_multiple': False},
    {'code': 'HR_PARTNER', 'label': 'HR Partner', 'derived_from_org_chart': False, 'allow_multiple': False},
    {'code': 'APPROVER', 'label': 'Approver', 'derived_from_org_chart': False, 'allow_multiple': False},
    {'code': 'DOTTED_LINE_MANAGER', 'label': 'Dotted-Line Manager', 'derived_from_org_chart': False, 'allow_multiple': False},
    {'code': 'MENTOR', 'label': 'Mentor', 'derived_from_org_chart': False, 'allow_multiple': True},
    {'code': 'BUDDY', 'label': 'Buddy', 'derived_from_org_chart': False, 'allow_multiple': True},
]

EMPLOYMENT_STATUSES = [
    {'code': 'PRE_JOINING', 'legacy_value': '', 'label': 'Pre-Joining', 'status_category': 'pre_joining'},
    {'code': 'PROBATION', 'legacy_value': 'probation', 'label': 'Probation', 'status_category': 'active'},
    {'code': 'CONFIRMED', 'legacy_value': 'confirmed', 'label': 'Confirmed', 'status_category': 'active'},
    {'code': 'NOTICE_PERIOD', 'legacy_value': '', 'label': 'Notice Period', 'status_category': 'active'},
    {'code': 'SUSPENDED', 'legacy_value': '', 'label': 'Suspended', 'status_category': 'inactive'},
    {'code': 'LONG_LEAVE', 'legacy_value': '', 'label': 'Long Leave', 'status_category': 'inactive'},
    {'code': 'SEPARATED', 'legacy_value': '', 'label': 'Separated', 'status_category': 'separated'},
    {'code': 'DECEASED', 'legacy_value': '', 'label': 'Deceased', 'status_category': 'separated'},
]


class Command(BaseCommand):
    help = 'Idempotently seed EMPLOYMENT_TYPE / EMPLOYMENT_STATUS lookups (Phase 5B Task A.1/A.2).'

    def handle(self, *args, **options):
        from django.core.cache import cache

        from apps.platform_core.models import LookupType, LookupValue

        created = updated = 0
        for lookup_code, name, rows in (
            ('EMPLOYMENT_TYPE', 'Employment Type', EMPLOYMENT_TYPES),
            ('EMPLOYMENT_STATUS', 'Employment Status', EMPLOYMENT_STATUSES),
            ('EMPLOYEE_RELATIONSHIP_TYPE', 'Employee Relationship Type', RELATIONSHIP_TYPES),
        ):
            lookup_type, _ = LookupType.objects.get_or_create(
                code=lookup_code, defaults={'name': name, 'module': 'accounts', 'is_system': True, 'allow_custom_values': True},
            )
            for order, spec in enumerate(rows):
                attributes = {k: v for k, v in spec.items() if k not in ('code', 'label', 'attrs')}
                attributes.update(spec.get('attrs', {}))
                attributes.setdefault('legacy_value', spec.get('legacy_value', ''))
                # update_or_create (not get_or_create): re-running this
                # command after a behavior-attribute change (e.g. this
                # phase's own fix to the nested 'attrs' bug) must correct
                # already-seeded rows, not silently leave stale attributes
                # in place forever.
                _, was_created = LookupValue.objects.update_or_create(
                    lookup_type=lookup_type, code=spec['code'],
                    defaults={'label': spec['label'], 'sort_order': order, 'attributes': attributes, 'is_system': True},
                )
                created += was_created
                updated += not was_created
            # services_employment_lookups caches resolved attributes for
            # 300s keyed by lookup_code — invalidate immediately so a
            # reseed takes effect without waiting out the TTL.
            cache.delete(f'employment_lookup_attrs:{lookup_code}')
        self.stdout.write(self.style.SUCCESS(f'Employment lookups seeded. Created={created} Updated={updated}'))
