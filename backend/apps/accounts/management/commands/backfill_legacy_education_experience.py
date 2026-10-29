from django.core.management.base import BaseCommand

from apps.accounts.models import EducationRecord, User, WorkExperienceRecord
from apps.accounts.services_education_experience import sync_legacy_education_experience_fields


class Command(BaseCommand):
    help = (
        'Backfills the legacy EmployeeProfile education/experience summary fields '
        '(highest_qualification, institution, specialization, year_of_passing, '
        'total_experience_years, previous_employer, previous_designation, leaving_reason) '
        'for employees whose EducationRecord/WorkExperienceRecord rows were created '
        'without going through add_education()/add_experience() -- the Hire Wizard '
        "completion path skipped the sync before this fix, leaving those employees' "
        'Profile & Experience tab blank despite having real records (UAT-022). '
        'Idempotent: safe to re-run.'
    )

    def handle(self, *args, **options):
        employee_ids = set(
            EducationRecord.objects.values_list('employee_id', flat=True)
        ) | set(
            WorkExperienceRecord.objects.values_list('employee_id', flat=True)
        )
        synced = 0
        for employee in User.objects.filter(id__in=employee_ids):
            sync_legacy_education_experience_fields(employee)
            synced += 1
        self.stdout.write(self.style.SUCCESS(f'Synced legacy education/experience fields for {synced} employee(s).'))
