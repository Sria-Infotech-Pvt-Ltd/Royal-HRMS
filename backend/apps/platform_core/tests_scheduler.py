"""Phase 3B Task G — scheduler locking and run-history tests."""
from __future__ import annotations

from django.test import TestCase

from apps.platform_core import services_scheduler as scheduler
from apps.platform_core.models import JobRun, JobType, ScheduledJob


class SchedulerTests(TestCase):
    def setUp(self):
        self.job_type = JobType.objects.create(
            code='test_job', name='Test Job', task_path='apps.platform_core.job_runners.drain_event_outbox',
            safe_to_run_concurrently=True,
        )
        self.job = ScheduledJob.objects.create(job_type=self.job_type, name='Test scheduled job', cron_expression='* * * * *')

    def test_run_now_creates_a_successful_job_run(self):
        run = scheduler.run_now(self.job.pk)
        self.assertEqual(run.status, JobRun.STATUS_SUCCESS)
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_running)
        self.assertIsNotNone(self.job.last_run_at)

    def test_run_now_records_failure_without_crashing(self):
        self.job_type.task_path = 'apps.platform_core.job_runners.nonexistent_function'
        self.job_type.save()
        run = scheduler.run_now(self.job.pk)
        self.assertEqual(run.status, JobRun.STATUS_FAILED)
        self.assertTrue(run.error_summary)
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_running)  # lock released even on failure

    def test_concurrent_run_blocked_unless_safe(self):
        self.job_type.safe_to_run_concurrently = False
        self.job_type.save()
        self.job.is_running = True
        self.job.save()
        with self.assertRaises(scheduler.SchedulerError):
            scheduler.run_now(self.job.pk)

    def test_concurrent_run_allowed_when_marked_safe(self):
        self.job.is_running = True
        self.job.save()
        run = scheduler.run_now(self.job.pk)  # job_type.safe_to_run_concurrently=True from setUp
        self.assertEqual(run.status, JobRun.STATUS_SUCCESS)

    def test_overdue_scheduled_jobs_detection(self):
        import datetime
        from django.utils import timezone
        self.job.next_run_at = timezone.now() - datetime.timedelta(hours=1)
        self.job.save()
        overdue = scheduler.overdue_scheduled_jobs(grace_minutes=30)
        self.assertIn(self.job, overdue)
