"""
One-off dummy-data generator: 1 manager + 1 HR + 7 employees, Hyderabad branch,
with July 2026 attendance + leave data, for testing a payroll run.

Run with: manage.py gen_hyderabad_test_data
Not wired into any URL/schedule -- delete this file after use if it should
not remain in the codebase long-term.
"""
import calendar
from datetime import date, time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Department, Designation, EmployeeProfile, Role, User
from apps.attendance.models import AttendanceRecord
from apps.branch.models import Branch
from apps.hrms.models import LeaveBalance, LeaveRequest
from apps.payroll.models import EmployeeSalaryConfig

BRANCH_NAME = "Hyderabad"
JOIN_DATE = date(2025, 6, 1)
YEAR, MONTH = 2026, 7


class Command(BaseCommand):
    help = "Generate 1 manager + 1 HR + 7 employees for Hyderabad with July 2026 attendance/leave data."

    def handle(self, *args, **options):
        days_in_month = calendar.monthrange(YEAR, MONTH)[1]

        Branch.objects.get(branch_name=BRANCH_NAME)  # sanity check it exists
        manager_role = Role.objects.get(name="manager__team_lead")
        hr_role = Role.objects.get(name="hr")
        employee_role = Role.objects.get(name="employee")
        eng_dept = Department.objects.get(name="Engineering")

        Designation.objects.get_or_create(name="Software Engineer", department=eng_dept)
        Designation.objects.get_or_create(name="Engineering Manager", department=eng_dept)

        def make_user(first, last, role, designation, department, ctc, suffix):
            email = f"{first.lower()}.{last.lower()}.hyd@example.com"
            user = User.objects.create_user(
                email=email,
                password="Test@12345",
                full_name=f"{first} {last}",
                role=role,
                department=department,
                designation=designation,
                branch=BRANCH_NAME,
                phone="9000000" + suffix[-3:],
                date_of_joining=JOIN_DATE,
                must_change_password=False,
                onboarding_status=User.ONBOARDING_COMPLETE,
                assessment_status=User.ASSESSMENT_COMPLETE,
            )
            EmployeeProfile.objects.get_or_create(
                user=user,
                defaults=dict(
                    date_of_birth=date(1995, 1, 1),
                    gender="male",
                    marital_status="single",
                    current_address="Test Address, Hyderabad",
                    account_holder_name=user.full_name,
                    account_type="savings",
                    account_number="00110022003300" + suffix[-2:],
                    ifsc_code="HDFC0001234",
                    bank_name="HDFC Bank",
                    bank_branch_name="Hyderabad Branch",
                    uan_number="10000000" + suffix[-4:],
                    pan_number=f"TESTP{suffix}A",
                ),
            )
            EmployeeSalaryConfig.objects.create(
                employee=user,
                annual_ctc=Decimal(ctc),
                salary_structure=None,
                effective_from=JOIN_DATE,
                is_active=True,
            )
            LeaveBalance.objects.bulk_create([
                LeaveBalance(employee=user, leave_type=lt, year=YEAR, total_days=Decimal(total), used_days=Decimal("0"))
                for lt, total in (("casual", 7), ("sick", 12), ("earned", 15))
            ])
            return user

        with transaction.atomic():
            manager = make_user("Test", "Manager", manager_role, "Engineering Manager", "Engineering", 1800000, "0187")
            hr = make_user("Test", "HR", hr_role, "HR Executive", "Human Resource", 1200000, "0188")

            employees = []
            ctcs = [600000, 650000, 700000, 750000, 800000, 850000, 900000]
            for i in range(1, 8):
                emp = make_user(
                    "Test", f"Employee{i}", employee_role, "Software Engineer", "Engineering",
                    ctcs[i - 1], f"{188 + i:04d}",
                )
                emp.reporting_manager = manager
                emp.hr = hr
                emp.save(update_fields=["reporting_manager", "hr", "updated_at"])
                employees.append(emp)

            all_people = [manager, hr] + employees
            manager.hr = hr
            manager.save(update_fields=["hr", "updated_at"])
            hr.reporting_manager = manager
            hr.save(update_fields=["reporting_manager", "updated_at"])

            leave_plan = {
                employees[0]: [("casual", 10)],
                employees[1]: [("sick", 12)],
                employees[5]: [("casual", 20)],
                employees[6]: [("sick", 15)],
            }
            half_day_plan = {employees[1]: [14]}
            absence_plan = {employees[2]: [8], employees[5]: [22]}
            late_plan = {employees[4]: [7, 21]}
            leave_dates_by_emp = {emp: {d for _, d in days} for emp, days in leave_plan.items()}

            # Build every AttendanceRecord in memory first, then a single
            # bulk_create -- 279 individual update_or_create() round-trips
            # here proved to hang unpredictably on this dev machine (shared
            # with a live runserver + celery worker + celery beat all hitting
            # the same DB); one bulk statement sidesteps that entirely and is
            # also just objectively faster.
            records = []
            for person in all_people:
                for day in range(1, days_in_month + 1):
                    d = date(YEAR, MONTH, day)
                    if d.weekday() >= 5:
                        records.append(AttendanceRecord(
                            employee=person, date=d, status=AttendanceRecord.STATUS_WEEKLY_OFF,
                        ))
                        continue

                    is_leave = day in leave_dates_by_emp.get(person, set())
                    is_absent = day in absence_plan.get(person, [])
                    is_half = day in half_day_plan.get(person, [])
                    is_late = day in late_plan.get(person, [])

                    if is_leave:
                        status, p_in, p_out, mins = AttendanceRecord.STATUS_ON_LEAVE, None, None, 0
                    elif is_absent:
                        status, p_in, p_out, mins = AttendanceRecord.STATUS_ABSENT, None, None, 0
                    elif is_half:
                        status, p_in, p_out, mins = AttendanceRecord.STATUS_HALF_DAY, time(9, 10), time(13, 30), 260
                    elif is_late:
                        status, p_in, p_out, mins = AttendanceRecord.STATUS_LATE, time(10, 20), time(18, 30), 490
                    else:
                        status, p_in, p_out, mins = AttendanceRecord.STATUS_PRESENT, time(9, 5), time(18, 10), 485

                    records.append(AttendanceRecord(
                        employee=person, date=d, status=status,
                        first_punch_in=p_in, last_punch_out=p_out,
                        total_working_minutes=mins, is_late=is_late,
                    ))

            AttendanceRecord.objects.bulk_create(records)

            for person, days in leave_plan.items():
                for leave_type, day in days:
                    start = date(YEAR, MONTH, day)
                    LeaveRequest.objects.create(
                        employee=person, leave_type=leave_type, duration="full_day",
                        start_date=start, end_date=start, total_days=Decimal("1"),
                        lop_days=Decimal("0"), reason="Test data - generated for payroll testing.",
                        status="approved",
                    )
                    bal = LeaveBalance.objects.get(employee=person, leave_type=leave_type, year=YEAR)
                    bal.used_days += Decimal("1")
                    bal.save(update_fields=["used_days"])

            self.stdout.write("Created:")
            self.stdout.write(f" Manager: {manager.employee_id} {manager.email}")
            self.stdout.write(f" HR:      {hr.employee_id} {hr.email}")
            for e in employees:
                cfg = EmployeeSalaryConfig.objects.get(employee=e)
                self.stdout.write(f" Employee: {e.employee_id} {e.email} CTC: {cfg.annual_ctc}")
