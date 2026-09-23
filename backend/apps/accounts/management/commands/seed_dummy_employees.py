"""
Management command: seed_dummy_employees

DEMO / TEST DATA ONLY. Creates a batch of realistic-but-fake employees
against real, already-seeded Positions/OrgUnits/Branches/LeavePolicies, so
the Employee Directory (pagination, org-unit hierarchy column, status
mix, KPIs) has enough rows to actually verify against the reference UI.
Never run this against a production tenant — these are placeholder people,
not real hires.

Mirrors the real hire path (EmployeeListCreateView.post) as closely as
makes sense for a bulk seed: creates the User, calls the same
assign_position()/leave-allocation/weekly-off-assignment functions real
hires go through — but skips sending any welcome email (nobody should get
a real email for a fake employee) and skips assessment assignment (not
needed to see the directory/table UI).

Run:  python manage.py seed_dummy_employees --dry-run
      python manage.py seed_dummy_employees
      python manage.py seed_dummy_employees --count 20
"""
import random
import secrets
import string
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import EmployeeCodeSettings, OrgUnit, Placement, Position, Role, User
from apps.accounts.services_placement import assign_position

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Ishaan", "Kabir", "Rohan", "Karthik", "Nikhil",
    "Sanjay", "Varun", "Ananya", "Diya", "Isha", "Kavya", "Meera", "Neha",
    "Pooja", "Riya", "Sneha", "Tanvi",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Reddy", "Rao", "Nair", "Iyer", "Menon",
    "Patil", "Kulkarni", "Bose", "Chatterjee", "Pillai", "Shetty", "Naidu",
]

# Real OrgUnits already seeded (0116_seed_sria_org_structure) — spread
# across a handful of real departments so the directory shows variety, not
# every dummy employee stacked into one unit.
TARGET_UNIT_NAMES = [
    "AI & ML", "Application Development", "Web", "Mobile", "SAP",
    "Testing / QA", "Cyber Security", "Digital Marketing",
    "Human Resources", "Finance & Accounts", "Sales & Marketing",
]

EMPLOYMENT_TYPES = ["Permanent", "Permanent", "Permanent", "Contract", "Intern"]


class Command(BaseCommand):
    help = "Seed realistic dummy employees onto real, existing positions for UI verification."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=15, help="Number of dummy employees to create.")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be created without saving.")

    def handle(self, *args, **options):
        count = options["count"]
        dry_run = options["dry_run"]

        employee_role = Role.objects.filter(name="employee").first()
        if employee_role is None:
            self.stderr.write(self.style.ERROR('No "employee" role found — run the base role/permission seed first.'))
            return

        units = list(OrgUnit.objects.filter(name__in=TARGET_UNIT_NAMES, is_active=True))
        if not units:
            self.stderr.write(self.style.ERROR("None of the target org units exist — is 0116_seed_sria_org_structure applied?"))
            return

        # Positions with ANY placement history at all (open or closed) are
        # excluded, not just ones with a currently-open placement — a joining
        # date picked at random could otherwise land inside/before an
        # existing closed placement's date range and trip the DB's
        # "no overlapping placement" constraint. A position with zero
        # placement history has nothing to collide with, at any date.
        positions_with_history = set(Placement.objects.values_list("position_id", flat=True).distinct())
        vacant_positions = list(
            Position.objects.filter(org_unit__in=units, is_active=True).exclude(id__in=positions_with_history)
        )
        random.shuffle(vacant_positions)
        if len(vacant_positions) < count:
            self.stdout.write(self.style.WARNING(
                f"Only {len(vacant_positions)} vacant positions in the target units — creating that many instead of {count}."
            ))
            count = len(vacant_positions)

        existing_emails = set(User.objects.values_list("email", flat=True))
        today = timezone.localdate()

        plan = []
        used_names = set()
        for i in range(count):
            while True:
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                if (first, last) not in used_names:
                    used_names.add((first, last))
                    break
            email = f"{first.lower()}.{last.lower()}.demo{i}@example.com"
            if email in existing_emails:
                email = f"{first.lower()}.{last.lower()}.demo{i}.{random.randint(100, 999)}@example.com"

            # Spread joining dates over the last ~2 years plus a couple this
            # week, so "+N this month" / "N joining this week" KPIs have
            # something real to count.
            if i < 2:
                joining = today - timedelta(days=random.randint(0, 6))
            else:
                joining = today - timedelta(days=random.randint(14, 730))

            # ~70% land as immediately active (must_change_password cleared),
            # ~25% stay in onboarding (the real hire default), ~5% get an
            # active separation so "Notice Period" has a real row to show.
            roll = random.random()
            outcome = "active" if roll < 0.70 else ("notice_period" if roll < 0.75 else "onboarding")

            plan.append({
                "first": first, "last": last, "email": email,
                "position": vacant_positions[i], "joining": joining,
                "employment_type": random.choice(EMPLOYMENT_TYPES),
                "outcome": outcome,
            })

        if dry_run:
            for p in plan:
                self.stdout.write(f"{p['first']} {p['last']} <{p['email']}> -> {p['position'].title} ({p['position'].org_unit.name}), "
                                   f"joined {p['joining']}, {p['outcome']}")
            self.stdout.write(self.style.SUCCESS(f"[dry-run] Would create {len(plan)} employees."))
            return

        created = []
        with transaction.atomic():
            for p in plan:
                employee_id = EmployeeCodeSettings.generate_employee_id(
                    first_name=p["first"], last_name=p["last"], date_of_joining=p["joining"],
                )
                temp_password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                user = User.objects.create_user(
                    email=p["email"],
                    password=temp_password,
                    full_name=f"{p['first']} {p['last']}",
                    role=employee_role,
                    employee_id=employee_id,
                    department="",
                    designation="",
                    branch="",
                    phone="",
                    employee_type=p["employment_type"],
                    date_of_joining=p["joining"],
                    must_change_password=(p["outcome"] == "onboarding"),
                    onboarding_status=(User.ONBOARDING_PENDING if p["outcome"] == "onboarding" else User.ONBOARDING_COMPLETE),
                )
                position = p["position"]
                assign_position(user, position, effective_from=p["joining"])
                user.refresh_from_db()
                if not user.branch:
                    from apps.branch.models import Branch
                    default_branch = Branch.objects.filter(status=Branch.STATUS_ACTIVE).first()
                    if default_branch:
                        user.branch = default_branch.branch_name
                        user.save(update_fields=["branch", "updated_at"])

                from apps.hrms.views.leave_shared import _allocate_leaves_for_employee
                _allocate_leaves_for_employee(user, user.date_of_joining)

                from apps.attendance.models import WeeklyDayPolicy
                from apps.attendance.services_hr import assign_weekly_off
                default_policy = WeeklyDayPolicy.objects.filter(is_default=True, is_active=True).first()
                if default_policy is not None:
                    assign_weekly_off(employee_id, default_policy, p["joining"], actor=None)

                if p["outcome"] == "notice_period":
                    from apps.hrms.models import SEP_APPROVED, SEPARATION_RESIGNATION, SeparationRequest
                    from django.db.models import Max
                    last_num = SeparationRequest.objects.aggregate(n=Max("request_number"))["n"] or 0
                    SeparationRequest.objects.create(
                        employee=user,
                        request_number=last_num + 1,
                        separation_type=SEPARATION_RESIGNATION,
                        reason="better_career_opportunity",
                        request_date=today,
                        proposed_last_working_day=today + timedelta(days=random.choice([30, 45, 60])),
                        notice_period_days=60,
                        # SEP_APPROVED, not just requested/pending — matches
                        # EmployeeStatsView's own "notice_period" KPI
                        # definition (see _employee_dict's identical filter),
                        # so the seeded row actually counts in both places.
                        status=SEP_APPROVED,
                        created_by=user,
                    )

                created.append(user)

        for user in created:
            self.stdout.write(f"  {user.employee_id}  {user.full_name}  {user.department} / {user.designation}")
        self.stdout.write(self.style.SUCCESS(f"Created {len(created)} dummy employees."))
