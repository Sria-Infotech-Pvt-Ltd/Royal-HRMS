"""
Fixed demo data for the `seed_demo_workforce` command: a realistic Indian workforce, the four office locations,
public holidays and the payroll periods to run. Pure data — no database access — so it is easy to review.

Every email is on @example.com (a reserved domain: nothing sent there reaches a real mailbox) and ends in
`.wf@example.com`, which is how `seed_demo_workforce --cleanup` recognises the people it created.
"""
from datetime import date

EMAIL_SUFFIX = '.wf@example.com'
PASSWORD = 'demo@1'
CYCLE_TAG = 'DEMO-WORKFORCE'          # PayrollCycle.notes — marks cycles this seed created
HOLIDAY_TAG = 'Demo workforce seed'   # Holiday.description

ATTENDANCE_START = date(2026, 7, 1)

# (branch name, code, state, city, address, pin code, is_metro) — Hyderabad reuses the existing active branch.
LOCATIONS = {
    'Hyderabad': {'code': 'KDP', 'name': 'Kondapur Office', 'state': 'Telangana', 'pin': '500084', 'metro': False,
                  'address': 'Kondapur, Hyderabad'},
    'Bengaluru': {'code': 'BLR', 'name': 'Bengaluru Office', 'state': 'Karnataka', 'pin': '560103', 'metro': False,
                  'address': 'Bellandur, Outer Ring Road, Bengaluru'},
    'Pune':      {'code': 'PNQ', 'name': 'Pune Office', 'state': 'Maharashtra', 'pin': '411057', 'metro': False,
                  'address': 'Hinjewadi Phase 1, Pune'},
    'Chennai':   {'code': 'MAA', 'name': 'Chennai Office', 'state': 'Tamil Nadu', 'pin': '600096', 'metro': True,
                  'address': 'Perungudi, Old Mahabalipuram Road, Chennai'},
}

# Professional tax slabs (monthly gross → monthly PT), used only for states that have no StatutoryConfig yet.
PT_SLABS = {
    'Telangana':   [{'min': 0, 'max': 15000, 'amount': 0}, {'min': 15001, 'max': 20000, 'amount': 150},
                    {'min': 20001, 'max': None, 'amount': 200}],
    'Karnataka':   [{'min': 0, 'max': 24999, 'amount': 0}, {'min': 25000, 'max': None, 'amount': 200}],
    'Maharashtra': [{'min': 0, 'max': 7500, 'amount': 0}, {'min': 7501, 'max': 10000, 'amount': 175},
                    {'min': 10001, 'max': None, 'amount': 200}],
    'Tamil Nadu':  [{'min': 0, 'max': 21000, 'amount': 0}, {'min': 21001, 'max': 30000, 'amount': 100},
                    {'min': 30001, 'max': None, 'amount': 208}],
}

# (name, % of CTC) for the default salary structure, used only when the server has no default structure.
DEFAULT_STRUCTURE = ('Standard Structure', [('Basic', 'earning', 40), ('HRA', 'allowance', 20), ('Special Allowance', 'allowance', 40)])

# Company-wide public holidays across the attendance window and just beyond it.
HOLIDAYS = [
    ('Independence Day', date(2026, 8, 15), 'national'),
    ('Ganesh Chaturthi', date(2026, 9, 14), 'regional'),
    ('Gandhi Jayanti', date(2026, 10, 2), 'national'),
    ('Vijayadashami (Dussehra)', date(2026, 10, 20), 'regional'),
    ('Diwali', date(2026, 11, 8), 'regional'),
    ('Christmas Day', date(2026, 12, 25), 'national'),
]

# (cycle start, cycle end, pay date) — the company's 25th→24th cycle. Oldest first.
PERIODS = [
    (date(2026, 7, 25), date(2026, 8, 24), date(2026, 8, 30)),
    (date(2026, 8, 25), date(2026, 9, 24), date(2026, 9, 30)),
]

# (first name, last name, gender, city, org unit, date of joining, employee type). The first person listed for a
# city outside Hyderabad is that city's team lead (role "manager"); Hyderabad reports to manager@example.com.
ROSTER = [
    ('Venkata', 'Rao', 'male', 'Hyderabad', 'Cloud & DevOps', date(2022, 6, 13), 'Permanent'),
    ('Lakshmi', 'Reddy', 'female', 'Hyderabad', 'Product QA', date(2023, 1, 9), 'Permanent'),
    ('Sai Kiran', 'Goud', 'male', 'Hyderabad', 'SAP Functional', date(2021, 11, 22), 'Permanent'),
    ('Harika', 'Chowdary', 'female', 'Hyderabad', 'Marketing', date(2024, 2, 5), 'Permanent'),
    ('Imran', 'Qureshi', 'male', 'Hyderabad', 'IT Support / Helpdesk', date(2023, 8, 16), 'Permanent'),
    ('Swathi', 'Nandamuri', 'female', 'Hyderabad', 'Content & Courseware', date(2025, 3, 3), 'Permanent'),
    ('Praveen', 'Yadav', 'male', 'Hyderabad', 'Network & SysAdmin', date(2020, 9, 7), 'Permanent'),
    ('Sravya', 'Konda', 'female', 'Hyderabad', 'Pre-Sales', date(2026, 4, 20), 'Contract'),
    ('Suresh', 'Gowda', 'male', 'Bengaluru', 'Cloud & DevOps', date(2019, 7, 1), 'Permanent'),
    ('Deepa', 'Hegde', 'female', 'Bengaluru', 'Product QA', date(2022, 10, 17), 'Permanent'),
    ('Manjunath', 'Shetty', 'male', 'Bengaluru', 'Cyber Security', date(2023, 5, 29), 'Permanent'),
    ('Kavitha', 'Murthy', 'female', 'Bengaluru', 'SAP Technical (ABAP)', date(2021, 2, 8), 'Permanent'),
    ('Rakesh', 'Naik', 'male', 'Bengaluru', 'Administration & IT', date(2024, 9, 2), 'Permanent'),
    ('Pallavi', 'Bhat', 'female', 'Bengaluru', 'Quality & Compliance', date(2025, 11, 10), 'Permanent'),
    ('Omkar', 'Deshmukh', 'male', 'Pune', 'Cloud & DevOps', date(2020, 1, 20), 'Permanent'),
    ('Snehal', 'Kulkarni', 'female', 'Pune', 'Product QA', date(2022, 3, 14), 'Permanent'),
    ('Prathamesh', 'Joshi', 'male', 'Pune', 'SAP Functional', date(2023, 12, 4), 'Permanent'),
    ('Rutuja', 'Patil', 'female', 'Pune', 'Marketing', date(2026, 8, 31), 'Permanent'),
    ('Aniket', 'Pawar', 'male', 'Pune', 'IT Support / Helpdesk', date(2024, 6, 24), 'Permanent'),
    ('Karthikeyan', 'Subramanian', 'male', 'Chennai', 'Cloud & DevOps', date(2018, 10, 8), 'Permanent'),
    ('Meenakshi', 'Iyer', 'female', 'Chennai', 'Product QA', date(2021, 7, 19), 'Permanent'),
    ('Arun', 'Venkatesh', 'male', 'Chennai', 'Network & SysAdmin', date(2023, 4, 3), 'Permanent'),
    ('Nithya', 'Rajan', 'female', 'Chennai', 'Content & Courseware', date(2025, 1, 13), 'Permanent'),
    ('Balaji', 'Srinivasan', 'male', 'Chennai', 'Pre-Sales', date(2026, 1, 12), 'Intern'),
]


def email_for(first_name: str, last_name: str) -> str:
    local = f'{first_name}.{last_name}'.lower().replace(' ', '')
    return f'{local}{EMAIL_SUFFIX}'


def team_leads() -> dict:
    """City → (first name, last name) of that city's team lead; Hyderabad has none (manager@example.com leads)."""
    leads = {}
    for first, last, _gender, city, *_rest in ROSTER:
        if city != 'Hyderabad':
            leads.setdefault(city, (first, last))
    return leads
