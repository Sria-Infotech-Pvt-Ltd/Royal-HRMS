"""
What an employee can declare in the annual tax (investment) declaration — the
single source of truth for the UI (served by TaxDeclarationSchemaView), the
server-side validation (EmployeeTaxDeclarationSaveSerializer) and the TDS
estimate (services_income_tax), so the three can never disagree on a limit.

Modelled on how Keka, Zoho Payroll and greytHR collect declarations, and on
the particulars of Form 124 (the Income-tax Act 2025 successor to Form 12BB):
house rent with landlord details, home-loan interest with lender details, the
80C-type investments item by item, 80CCD(1B), health insurance (self/family and
parents separately, with the senior-citizen limit), education-loan interest,
donations and income from a previous employer.

Section numbers are shown as in the Income-tax Act 1961 (80C, 80D, ...), which
is what employees and every payroll tool still use; the Income-tax Act 2025
renumbers them (80C -> 123, 80D -> 126, 80CCD -> 127) with the same limits.

Storage: `EmployeeTaxDeclaration.declared_investments` stays one flat JSON dict
of {key: rupee amount}. The few non-numeric answers (rent/landlord details,
senior-citizen flags, previous-employer figures) live under the reserved key
`_details` of that same dict — a new column would need a payroll migration,
and the shared dev database already carries other branches' payroll migrations.

Keys '80C', '80D' and 'HRA' are the original single-number fields (HRA was an
exemption amount the employee worked out themselves); they are still honoured
so declarations saved before this schema keep producing the same TDS.
"""
from __future__ import annotations

import re
from decimal import Decimal

DETAILS_KEY = '_details'
MAX_DECLARED_AMOUNT = Decimal('100000000')  # sanity bound — Rs 10 crore

CAP_80C = Decimal('150000')
CAP_80CCD_1B = Decimal('50000')
CAP_80D_STANDARD = Decimal('25000')
CAP_80D_SENIOR = Decimal('50000')
CAP_80D_TOTAL = Decimal('100000')
CAP_24B_SELF_OCCUPIED = Decimal('200000')

# Annual rent above this needs the landlord's PAN (CBDT rule, carried into Form 124).
RENT_LANDLORD_PAN_THRESHOLD = Decimal('100000')

# Cities where HRA exemption is 50% of basic instead of 40% — eight cities from FY 2026-27
# (Income-tax Rules 2026; Bengaluru, Hyderabad, Pune and Ahmedabad were added to the original four).
METRO_CITIES = ['Delhi', 'Mumbai', 'Kolkata', 'Chennai', 'Bengaluru', 'Hyderabad', 'Pune', 'Ahmedabad']

PAN_PATTERN = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')

LANDLORD_RELATIONSHIPS = [
    ('none',      'Not related'),
    ('parent',    'Parent'),
    ('spouse',    'Spouse'),
    ('sibling',   'Sibling'),
    ('relative',  'Other relative'),
]

# Group -> (title, hint, combined cap or None). Order is display order.
GROUPS: list[dict] = [
    {
        'key': '80c', 'title': 'Section 80C — investments & payments',
        'hint': 'Combined limit of ₹1,50,000. Your own PF deducted from salary is counted by payroll automatically.',
        'cap': CAP_80C,
        'fields': [
            ('80C_PPF',                  'Public Provident Fund (PPF)',               'PPF passbook or deposit receipts'),
            ('80C_ELSS',                 'ELSS tax-saving mutual funds',              'Fund account statement'),
            ('80C_LIFE_INSURANCE',       'Life insurance premium',                    'Premium receipt or certificate'),
            ('80C_NSC',                  'National Savings Certificate (NSC)',        'NSC certificate'),
            ('80C_SUKANYA',              'Sukanya Samriddhi account',                 'Passbook or deposit receipts'),
            ('80C_TAX_SAVER_FD',         '5-year tax-saver fixed deposit',            'FD receipt or certificate'),
            ('80C_TUITION',              "Children's tuition fees (up to 2 children)", 'School or college fee receipts'),
            ('80C_HOME_LOAN_PRINCIPAL',  'Home loan principal repayment',             'Lender repayment certificate'),
            ('80C_OTHER',                'Other 80C investments',                     'Relevant receipt or statement'),
        ],
    },
    {
        'key': 'nps', 'title': 'Section 80CCD(1B) — additional NPS',
        'hint': 'Own NPS Tier-I contribution over and above the 80C limit — up to ₹50,000.',
        'cap': CAP_80CCD_1B,
        'fields': [
            ('80CCD1B', 'Additional NPS contribution', 'NPS (PRAN) contribution statement'),
        ],
    },
    {
        'key': '80d', 'title': 'Section 80D — health insurance',
        'hint': 'Self and family: up to ₹25,000 (₹50,000 if any of you is a senior citizen). Parents: up to ₹25,000 '
                '(₹50,000 if a parent is a senior citizen). Preventive health check-up counts within these limits.',
        'cap': CAP_80D_TOTAL,
        'fields': [
            ('80D_SELF_FAMILY', 'Premium — self, spouse and children', 'Insurer premium receipt'),
            ('80D_PARENTS',     'Premium — parents',                    'Insurer premium receipt'),
        ],
    },
    {
        'key': 'loans', 'title': 'Loan interest',
        'hint': None, 'cap': None,
        'fields': [
            ('24B', 'Home loan interest — self-occupied property (Section 24(b), up to ₹2,00,000)', 'Lender interest certificate'),
            ('80E', 'Education loan interest (Section 80E, no upper limit)',                        'Lender interest certificate'),
        ],
    },
    {
        'key': 'donations', 'title': 'Donations',
        'hint': None, 'cap': None,
        'fields': [
            ('80G', 'Donations to approved funds (Section 80G) — amount eligible for deduction', 'Donation receipt with 80G registration number'),
        ],
    },
]

# Per-field caps applied to a single declared key.
FIELD_CAPS: dict[str, Decimal] = {
    '80CCD1B': CAP_80CCD_1B,
    '24B': CAP_24B_SELF_OCCUPIED,
}

AMOUNT_KEYS: set[str] = {key for group in GROUPS for key, _label, _proof in group['fields']}
LEGACY_KEYS: set[str] = {'80C', '80D', 'HRA'}
ALLOWED_KEYS: set[str] = AMOUNT_KEYS | LEGACY_KEYS | {DETAILS_KEY}
KEYS_80C: set[str] = {key for key, _l, _p in GROUPS[0]['fields']}


def schema_payload() -> dict:
    """JSON-serialisable description of the form, for the frontend."""
    return {
        'groups': [
            {
                'key': group['key'], 'title': group['title'], 'hint': group['hint'],
                'cap': int(group['cap']) if group['cap'] is not None else None,
                'fields': [
                    {
                        'key': key, 'label': label, 'proof': proof,
                        'cap': int(FIELD_CAPS[key]) if key in FIELD_CAPS else None,
                    }
                    for key, label, proof in group['fields']
                ],
            }
            for group in GROUPS
        ],
        'landlord_relationships': [{'value': value, 'label': label} for value, label in LANDLORD_RELATIONSHIPS],
        'landlord_pan_threshold': int(RENT_LANDLORD_PAN_THRESHOLD),
        'metro_cities': METRO_CITIES,
        'senior_cap': int(CAP_80D_SENIOR),
        'standard_cap': int(CAP_80D_STANDARD),
    }
