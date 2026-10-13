"""Phase 8A Task B — checklist instance creation, relative due dates, dependencies."""
import datetime

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import ChecklistTaskTemplate, ChecklistTemplate
from apps.hrms.services_checklist import complete_task, create_instance_from_template

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


class ChecklistInstanceTests(TestCase):
    def test_relative_due_dates_computed_from_anchor(self):
        template = ChecklistTemplate.objects.create(code=_unique('TPL'), name='Onboarding', checklist_type=ChecklistTemplate.TYPE_ONBOARDING)
        ChecklistTaskTemplate.objects.create(
            template=template, title='Collect ID proof', due_offset_days=-3,
            assignee_resolver=ChecklistTaskTemplate.ASSIGNEE_HR, order=0,
        )
        ChecklistTaskTemplate.objects.create(
            template=template, title='Issue laptop', due_offset_days=0,
            assignee_resolver=ChecklistTaskTemplate.ASSIGNEE_EMPLOYEE, order=1,
        )
        employee = _make_employee()
        joining_date = datetime.date(2026, 5, 1)

        instance = create_instance_from_template(template, employee, joining_date)
        tasks = {t.task_template.title: t for t in instance.tasks.all()}
        self.assertEqual(tasks['Collect ID proof'].due_date, datetime.date(2026, 4, 28))
        self.assertEqual(tasks['Issue laptop'].due_date, datetime.date(2026, 5, 1))

    def test_dependent_task_is_blocked_until_dependency_completes(self):
        template = ChecklistTemplate.objects.create(code=_unique('TPL'), name='Onboarding')
        first = ChecklistTaskTemplate.objects.create(template=template, title='Sign offer', due_offset_days=0, order=0)
        ChecklistTaskTemplate.objects.create(template=template, title='Start IT setup', due_offset_days=1, order=1, depends_on=first)

        employee = _make_employee()
        instance = create_instance_from_template(template, employee, datetime.date(2026, 5, 1))
        dependent = instance.tasks.get(task_template__title='Start IT setup')
        self.assertEqual(dependent.status, dependent.STATUS_BLOCKED)

        first_task = instance.tasks.get(task_template__title='Sign offer')
        complete_task(first_task, employee)
        dependent.refresh_from_db()
        self.assertEqual(dependent.status, dependent.STATUS_PENDING)

    def test_checklist_marked_completed_once_every_task_is_done(self):
        template = ChecklistTemplate.objects.create(code=_unique('TPL'), name='Onboarding')
        ChecklistTaskTemplate.objects.create(template=template, title='Only task', due_offset_days=0, order=0)
        employee = _make_employee()
        instance = create_instance_from_template(template, employee, datetime.date(2026, 5, 1))
        task = instance.tasks.first()
        complete_task(task, employee)
        instance.refresh_from_db()
        self.assertEqual(instance.status, instance.STATUS_COMPLETED)
        self.assertIsNotNone(instance.completed_at)
