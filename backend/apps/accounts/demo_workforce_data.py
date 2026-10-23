"""
Fixed demo data for the `seed_demo_workforce` command: a realistic Indian workforce, the four office locations,
public holidays and the payroll periods to run. Pure data — no database access — so it is easy to review.

Every email is on @example.com (a reserved domain: nothing sent there reaches a real mailbox) and ends in
`.wf@example.com`, which is how `seed_demo_workforce --cleanup` recognises the people it created.
"""
from datetime import date, timedelta

EMAIL_SUFFIX = '.wf@example.com'
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

# (first name, last name, gender, city, org unit, date of joining, employee type).
# 100 reserved-domain synthetic employees, spread across 20 org units (five
# currently vacant seats each) and four offices. Type mix: 70 permanent,
# 20 contract and 10 intern. The roster is deterministic so reruns and
# cleanup remain safe. The first person in Bengaluru, Pune and Chennai is
# that office's team lead; Hyderabad reports to manager@example.com.
_FIRST_NAMES = [
    'Aarav', 'Ananya', 'Aditya', 'Diya', 'Arjun', 'Ishita', 'Vihaan', 'Aadhya', 'Reyansh', 'Saanvi',
    'Krishna', 'Myra', 'Dhruv', 'Kavya', 'Rohan', 'Meera', 'Ishaan', 'Tara', 'Kabir', 'Navya',
    'Ayaan', 'Pooja', 'Neel', 'Riya', 'Dev',
]
_LAST_NAMES = [
    'Rao', 'Reddy', 'Goud', 'Chowdary', 'Qureshi', 'Nandamuri', 'Yadav', 'Konda', 'Gowda', 'Hegde',
    'Shetty', 'Murthy', 'Naik', 'Bhat', 'Deshmukh', 'Kulkarni', 'Joshi', 'Patil', 'Pawar', 'Iyer',
    'Venkatesh', 'Rajan', 'Srinivasan', 'Menon', 'Sharma',
]
_UNITS = [
    'Admissions & Student Services', 'Automation', 'Cloud & DevOps', 'Content & Courseware',
    'Cyber Security', 'Manual', 'Mobile', 'Network & SysAdmin', 'Pre-Sales', 'Product Engineering',
    'Product Management', 'Product QA', 'Quality & Compliance', 'SAP Basis', 'SAP Functional',
    'SAP Technical (ABAP)', 'SEO & SEM', 'Sales', 'Social & Content', 'Talent Acquisition',
]
_ROSTER_BY_CITY = {city: [] for city in LOCATIONS}
for _unit_index, _unit in enumerate(_UNITS):
    for _seat_index in range(5):
        _i = _unit_index * 5 + _seat_index
        _first_index = _i % len(_FIRST_NAMES)
        _first = _FIRST_NAMES[_first_index]
        _last = _LAST_NAMES[(_first_index + (_i // len(_FIRST_NAMES)) * 7) % len(_LAST_NAMES)]
        _city = list(LOCATIONS)[(_unit_index + _seat_index) % len(LOCATIONS)]
        _joined = date(2018, 1, 1) + timedelta(days=(_i * 29) % 2980)
        _kind = 'Intern' if _i % 10 == 0 else ('Contract' if _i % 10 in (1, 2) else 'Permanent')
        _ROSTER_BY_CITY[_city].append((
            _first, _last, 'female' if _i % 2 else 'male', _city, _unit, _joined, _kind,
        ))
ROSTER = [row for city in LOCATIONS for row in _ROSTER_BY_CITY[city]]


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
