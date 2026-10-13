"""Phase 8B Task D — audience-rule migration parity, acknowledgement tracking."""
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.announcements.models import Announcement
from apps.announcements.services_announcements_v2 import (
    migrate_visibility_to_rule, pending_acknowledgers, record_acknowledgement,
    resolve_recipients_from_rule, resolve_recipients_legacy,
)

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee(**extra):
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!', **extra)


class AudienceRuleParityTests(TestCase):
    def test_visibility_all_resolves_to_empty_rule(self):
        announcement = Announcement.objects.create(title='x', body='x', category='general', visibility='all')
        rule = migrate_visibility_to_rule(announcement)
        self.assertEqual(rule.rule, {})

    def test_branch_visibility_resolves_same_recipients(self):
        from apps.branch.models import Branch, City, State
        state = State.objects.create(name=_unique('State'), code=_unique('S')[:10])
        city = City.objects.create(name=_unique('City'), state=state)
        branch = Branch.objects.create(branch_code=_unique('BR'), branch_name=_unique('Branch'), address='x', state=state, city=city)

        in_branch = _make_employee(branch=branch.branch_name)
        _make_employee()  # not in branch

        announcement = Announcement.objects.create(
            title='x', body='x', category='general', visibility='branch', target_branch=branch,
        )
        rule = migrate_visibility_to_rule(announcement)

        legacy_recipients = resolve_recipients_legacy(announcement)
        new_recipients = resolve_recipients_from_rule(rule)
        self.assertEqual(legacy_recipients, new_recipients)
        self.assertIn(in_branch.id, new_recipients)

    def test_migration_is_idempotent(self):
        announcement = Announcement.objects.create(title='x', body='x', category='general', visibility='all')
        first = migrate_visibility_to_rule(announcement)
        second = migrate_visibility_to_rule(announcement)
        self.assertEqual(first.id, second.id)


class AcknowledgementTests(TestCase):
    def test_pending_acknowledgers_shrinks_after_acknowledging(self):
        from apps.branch.models import Branch, City, State
        state = State.objects.create(name=_unique('State'), code=_unique('S')[:10])
        city = City.objects.create(name=_unique('City'), state=state)
        branch = Branch.objects.create(branch_code=_unique('BR'), branch_name=_unique('Branch'), address='x', state=state, city=city)
        employee = _make_employee(branch=branch.branch_name)

        announcement = Announcement.objects.create(
            title='x', body='x', category='general', visibility='branch', target_branch=branch,
        )
        rule = migrate_visibility_to_rule(announcement)

        pending_before = pending_acknowledgers(announcement)
        self.assertIn(employee.id, pending_before)

        record_acknowledgement(announcement, employee)
        pending_after = pending_acknowledgers(announcement)
        self.assertNotIn(employee.id, pending_after)
