"""
Deterministic FAKE personal details for demo employees.

DEMO / TEST DATA ONLY — used by the `seed_demo_employee_details` management
command to give seeded placeholder employees the same kind of complete record
the reference Employee Directory shows (date of birth, address, emergency
contact, government IDs, pay). Every value is derived from the employee's
number, so re-running the command always produces the same answer.

None of these values are real: PANs/Aadhaar/bank numbers are made-up strings
in the right shape, never issued to anyone.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

GENDERS      = ['female', 'male', 'female', 'male']
BLOODS       = ['O+', 'A+', 'B+', 'AB+', 'O-', 'A-', 'B-']
STATES       = ['Telangana', 'Telangana', 'Karnataka', 'Maharashtra']
CITIES       = ['Hyderabad', 'Hyderabad', 'Bengaluru', 'Pune']
PIN_CODES    = ['500032', '500084', '560066', '411014']
RELATIONSHIPS = ['Father', 'Mother', 'Spouse', 'Sibling']

# First names the dummy seeder draws from (plus a few reference-style ones), so a person's gender matches
# their name and avatar. Anything not listed falls back to a number-based pattern.
FEMALE_FIRST_NAMES = {
    'ananya', 'diya', 'isha', 'kavya', 'meera', 'neha', 'pooja', 'riya', 'sneha', 'tanvi',
    'priya', 'fatima', 'deepika', 'ishita', 'lakshmi', 'divya', 'swati', 'nandini', 'ritika',
    'shreya', 'maya', 'tanya', 'keerthi', 'bhavna', 'kriti', 'farah', 'aisha',
}
MALE_FIRST_NAMES = {
    'aarav', 'vivaan', 'aditya', 'ishaan', 'kabir', 'rohan', 'karthik', 'nikhil', 'sanjay', 'varun',
    'arjun', 'vikram', 'rahul', 'amit', 'rohit', 'suresh', 'sandeep', 'yash', 'nitin', 'karan', 'manoj',
    'harish', 'gaurav', 'vivek', 'akash', 'abhishek', 'sameer', 'joseph', 'omkar', 'tarun',
}

# Annual fixed CTC (INR) by seniority keyword found in the job title.
_CTC_BY_KEYWORD = [
    ('head', 2_400_000), ('director', 2_600_000), ('lead', 1_800_000), ('manager', 2_000_000),
    ('senior', 1_500_000), ('specialist', 1_100_000), ('associate ii', 600_000),
    ('trainee', 360_000), ('associate', 480_000), ('engineer', 900_000), ('administrator', 900_000),
    ('partner', 1_200_000),
]
_DEFAULT_CTC = 700_000


def employee_number(employee_id: str) -> int:
    """EMP00011 -> 11; QA0003 -> 3; anything without digits -> 1."""
    digits = re.search(r'\d+', employee_id or '')
    return int(digits.group()) if digits else 1


def _name_parts(full_name: str) -> tuple[str, str]:
    cleaned = re.sub(r'[^a-z ]', '', (full_name or 'employee profile').lower()).split()
    return (cleaned[0] if cleaned else 'employee', cleaned[-1] if cleaned else 'profile')


def personal_details(number: int, full_name: str) -> dict:
    """Fields for EmployeeProfile (personal, address, emergency contact)."""
    first, last = _name_parts(full_name)
    city = CITIES[number % len(CITIES)]
    if first in FEMALE_FIRST_NAMES:
        gender = 'female'
    elif first in MALE_FIRST_NAMES:
        gender = 'male'
    else:
        gender = GENDERS[number % len(GENDERS)]
    return {
        'salutation':             'Ms' if gender == 'female' else 'Mr',
        'middle_name':            'Kumar' if number % 2 else '',
        'display_name':           f'{first.title()} {last.title()}',
        'date_of_birth':          date(1978 + (number * 7) % 23, 1 + (number * 5) % 12, 1 + (number * 11) % 27),
        'gender':                 gender,
        'place_of_birth':         city,
        'blood_group':            BLOODS[number % len(BLOODS)],
        'marital_status':         'married' if number % 3 == 0 else 'single',
        'nationality':            'Indian',
        'father_name':            f'Demo Father {number:03d}',
        'mother_name':            f'Demo Mother {number:03d}',
        'languages_known':        'English, Hindi, Telugu',
        'personal_email':         f'{first}.{last}.demo@example.com',
        'current_address':        f'Flat {100 + number}, AIRA Demo Residency',
        'current_address_line2':  f'Block {1 + number % 12}, Floor {1 + number % 8}',
        'current_village':        city,
        'current_district':       city,
        'current_state':          STATES[number % len(STATES)],
        'current_pin_code':       PIN_CODES[number % len(PIN_CODES)],
        'permanent_same_as_current': number % 2 == 0,
        'permanent_address':      f'House {200 + number}, AIRA Demo Colony',
        'permanent_address_line2': f'Ward {1 + number % 20}',
        'permanent_village':      city,
        'permanent_district':     city,
        'permanent_state':        STATES[number % len(STATES)],
        'permanent_pin_code':     PIN_CODES[number % len(PIN_CODES)],
        'highest_qualification':  ('Bachelor of Engineering', 'Bachelor of Commerce', 'Master of Business Administration', 'Bachelor of Science')[number % 4],
        'institution':            'AIRA Demo University',
        'year_of_passing':        2000 + number % 23,
        'specialization':         ('Information Technology', 'Finance', 'Operations', 'Business Administration')[number % 4],
        'total_experience_years': Decimal(f'{1 + number % 15}.0'),
        'previous_employer':      'AIRA Demo Systems',
        'previous_designation':   'Associate',
        'leaving_reason':         'Career progression',
        'core_skills':            'Communication, collaboration, role-specific skills',
        'emergency_name':         f'Demo Contact {number:02d}',
        'emergency_relationship': RELATIONSHIPS[number % len(RELATIONSHIPS)],
        'emergency_phone':        f'+91 91111 {str(20000 + number)[-5:]}',
        'emergency_email':        f'emergency{number:03d}@example.com',
    }


def mobile_number(number: int) -> str:
    return f'+91 90000 {str(10000 + number)[-5:]}'


def statutory_and_bank(number: int, full_name: str) -> dict:
    """Made-up PAN / Aadhaar / bank values in the right shape."""
    return {
        'pan_number':          f'DEMOP{number:04d}X',
        'aadhaar_number':      f'4521{88900000 + number:08d}',
        'name_as_per_aadhar':  full_name,
        'uan_number':          str(100000000000 + number),
        'pf_number':           f'PF/DEMO/{number:06d}',
        'account_holder_name': full_name,
        'account_type':        'savings',
        'account_number':      f'50100234{number:04d}',
        'ifsc_code':           'HDFC0001234',
        'bank_name':           'HDFC Bank',
        'bank_branch_name':    'Kondapur',
    }


def annual_ctc_for(title: str) -> int:
    lowered = (title or '').lower()
    for keyword, amount in _CTC_BY_KEYWORD:
        if keyword in lowered:
            return amount
    return _DEFAULT_CTC


def joining_date(number: int, today: date) -> date:
    """A believable spread of joining dates (2018 onwards) that is never in the future."""
    candidate = date(2018 + number % 8, 1 + (number * 5) % 12, 1 + (number * 11) % 27)
    return candidate if candidate < today else date(today.year - 1, candidate.month, candidate.day)


def lifecycle_bucket(number: int) -> str:
    """'onboarding' (about 1 in 10), 'probation' (about 1 in 10), otherwise 'active'."""
    remainder = number % 10
    if remainder == 3:
        return 'onboarding'
    if remainder == 7:
        return 'probation'
    return 'active'
