"""
Bulk employee import from an Excel workbook: reading the file and validating every row, without writing anything.

Preview and commit both call validate_rows(), so what the HR user sees in the preview is exactly what the commit
re-checks. Nothing in this module creates or changes data.

Rules:
  - the columns are fixed (COLUMNS); nothing sensitive (bank, PAN, Aadhaar, UAN, CTC, passwords) is read at all;
  - branch, org unit, position and reporting manager must already exist and match exactly; nothing is guessed or created.
    Several seats may share one org unit and title: each row gets the first vacant one (services_employee_import_seats);
  - a non-admin importer may only import into their own branch, whatever the spreadsheet says (checked here, on the
    server, for preview and for commit);
  - an email that already exists, or repeats in the file, is reported as a duplicate, never skipped silently.
"""
from __future__ import annotations

import datetime
import hashlib
import io
import re
from dataclasses import dataclass, field

from apps.accounts.employment_types import normalize_employment_type

from apps.accounts.models import EmployeeProfile, Position, User
from apps.accounts.services_employee_import_seats import SeatPool
from apps.accounts.services_approver_assignment import KIND_REPORTING_MANAGER, approver_refusal
from core.access import is_full_access
from core.permissions import has_perm

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 500
EMPLOYEES_SHEET = 'Employees'

PHONE_RE = re.compile(r'^(?:\+?91)?\d{10}$')
_PHONE_FORMATTING_RE = re.compile(r'[\s\-()./]')
NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:[ '\-][A-Za-z0-9]+)*$")
EMAIL_RE = re.compile(
    r'^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$'
)
ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
PIN_RE = re.compile(r'^\d{6}$')


@dataclass(frozen=True)
class Column:
    key: str
    header: str
    required: bool
    description: str
    example: str
    # Shown in the preview and in the error report. Personal details are read and imported but never echoed back.
    is_core: bool = True


COLUMNS: tuple[Column, ...] = (
    Column('first_name', 'First Name', True, 'Given name. Letters, numbers, spaces, hyphens and apostrophes.', 'Asha'),
    Column('last_name', 'Last Name', True, 'Family name. Same characters as First Name.', 'Verma'),
    Column('email', 'Work Email', True, 'Company email. Must be unique: no one in HRMS or in this file may already use it.', 'asha.verma@company.com'),
    Column('date_of_joining', 'Date of Joining', True, 'YYYY-MM-DD.', '2026-11-10'),
    Column('branch', 'Company Code', True, 'The branch code (or exact branch name) of an active branch. Pick from the dropdown.', 'KDP'),
    Column('org_unit', 'Org Unit', True, 'Exact name of an existing org unit. Pick from the dropdown.', 'Software Services'),
    Column('position', 'Position', True, 'Exact title of an active position inside that org unit (see the Lists sheet for valid pairs).', 'Software Engineer'),
    Column('employee_type', 'Employment Type', False, 'Permanent, Contract, Freelancer, Consultant, Part-Time, Temporary or Intern. Blank means Permanent.', 'Permanent'),
    Column('phone', 'Mobile Number', False, '10 digits, optionally with +91 or 91 and spaces or hyphens.', '9876543210', is_core=False),
    Column('reporting_manager', 'Reporting Manager Employee ID', False, 'Employee ID of an existing, active manager. Leave blank to use the org chart. Not allowed for manager positions.', '10000004'),
    Column('personal_email', 'Personal Email', False, 'A valid personal email address.', 'asha@example.com', is_core=False),
    Column('gender', 'Gender', False, 'Male, Female or Other.', 'Female', is_core=False),
    Column('date_of_birth', 'Date of Birth', False, 'YYYY-MM-DD, in the past.', '1995-06-20', is_core=False),
    Column('blood_group', 'Blood Group', False, 'A+, A-, B+, B-, O+, O-, AB+ or AB-.', 'B+', is_core=False),
    Column('address_line1', 'Address Line 1', False, 'Current address.', '12 Main Street', is_core=False),
    Column('address_line2', 'Address Line 2', False, 'Current address, second line.', 'Kondapur', is_core=False),
    Column('district', 'District', False, 'Current district or city.', 'Hyderabad', is_core=False),
    Column('state', 'State', False, 'Current state.', 'Telangana', is_core=False),
    Column('pin_code', 'PIN Code', False, 'Exactly 6 digits.', '500084', is_core=False),
    Column('emergency_name', 'Emergency Contact Name', False, 'Who to call in an emergency.', 'Ravi Verma', is_core=False),
    Column('emergency_relationship', 'Emergency Contact Relationship', False, 'For example Father, Spouse.', 'Father', is_core=False),
    Column('emergency_phone', 'Emergency Contact Number', False, 'Same format as Mobile Number.', '9876543211', is_core=False),
)
BY_HEADER = {column.header.lower(): column for column in COLUMNS}
REQUIRED_KEYS = tuple(column.key for column in COLUMNS if column.required)

GENDERS = {'male': EmployeeProfile.GENDER_MALE, 'female': EmployeeProfile.GENDER_FEMALE, 'other': EmployeeProfile.GENDER_OTHER}
BLOOD_GROUPS = {value.lower(): value for value, _label in EmployeeProfile.BLOOD_CHOICES}


class ImportFileError(Exception):
    """The file itself cannot be used; the message is safe to show."""


def file_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _cell_text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


@dataclass
class ParsedFile:
    rows: list[tuple[int, dict]] = field(default_factory=list)      # (Excel row number, {column key: text})


def parse_workbook(content: bytes, *, max_rows: int = MAX_ROWS) -> ParsedFile:
    """Rows of the Employees sheet keyed by column, with Excel row numbers. Blank rows are ignored.
    `max_rows` is 500 for the synchronous import; the background import job passes its own, larger limit."""
    if len(content) > MAX_FILE_BYTES:
        raise ImportFileError('The file is too large. The maximum size is 5 MB.')
    if not content.startswith(b'PK'):
        raise ImportFileError('This is not an Excel (.xlsx) file. Download the template and fill that in.')
    try:
        import openpyxl

        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise ImportFileError('The file could not be read as an Excel workbook. It may be damaged or password protected.')
    try:
        sheet = workbook[EMPLOYEES_SHEET] if EMPLOYEES_SHEET in workbook.sheetnames else workbook.worksheets[0]
        iterator = sheet.iter_rows(values_only=True)
        try:
            header_cells = next(iterator)
        except StopIteration:
            raise ImportFileError(f'The "{EMPLOYEES_SHEET}" sheet is empty. Use the template.')
        mapping: dict[int, str] = {}
        for index, cell in enumerate(header_cells):
            # The template marks required headers with a trailing " *".
            column = BY_HEADER.get(_cell_text(cell).rstrip(' *').lower())
            if column is not None:
                mapping[index] = column.key
        missing = [column.header for column in COLUMNS if column.required and column.key not in mapping.values()]
        if missing:
            raise ImportFileError('The header row is missing required columns: ' + ', '.join(missing) + '. Use the template.')
        parsed = ParsedFile()
        for excel_row, cells in enumerate(iterator, start=2):
            values = {mapping[i]: _cell_text(cells[i]) for i in mapping if i < len(cells)}
            if not any(values.values()):
                continue
            parsed.rows.append((excel_row, values))
            if len(parsed.rows) > max_rows:
                raise ImportFileError(f'The file has more than {max_rows} employees. Split it into smaller files.')
        if not parsed.rows:
            raise ImportFileError('The file has no employee rows.')
        return parsed
    finally:
        workbook.close()


# ── Who may import into which branch ────────────────────────────────────────

def is_branch_admin_user(user: User) -> bool:
    """Full-access users and settings.edit holders choose among all active branches; everyone else has their own."""
    return is_full_access(user) or has_perm(user, 'settings.edit')


def allowed_branches(user: User):
    """The active branches this importer may import into: all of them for an admin, otherwise only their own."""
    from apps.branch.models import Branch

    active = Branch.objects.filter(status=Branch.STATUS_ACTIVE)
    if is_branch_admin_user(user):
        return list(active.order_by('branch_name'))
    own_name = (user.branch or '').strip().lower()
    return [branch for branch in active.order_by('branch_name')
            if (user.branch_fk_id and branch.pk == user.branch_fk_id) or (own_name and branch.branch_name.strip().lower() == own_name)]


@dataclass
class RowResult:
    row: int
    values: dict
    errors: list[str] = field(default_factory=list)
    is_duplicate: bool = False
    branch_name: str = ''
    position: Position | None = None
    manager: User | None = None
    employee_type: str = 'Permanent'
    date_of_joining: datetime.date | None = None
    date_of_birth: datetime.date | None = None

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def status(self) -> str:
        if not self.errors:
            return 'valid'
        return 'duplicate' if self.is_duplicate and all(e.startswith('Duplicate') for e in self.errors) else 'invalid'


def _valid_phone(raw: str) -> bool:
    return bool(PHONE_RE.match(_PHONE_FORMATTING_RE.sub('', raw)))


def _iso_date(raw: str) -> datetime.date | None:
    if not ISO_DATE_RE.match(raw):
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None


class _Lookups:
    """Everything a validation pass needs, loaded once for the whole file."""

    def __init__(self, importer: User, rows: list[tuple[int, dict]]):
        self.importer = importer
        self.is_admin = is_branch_admin_user(importer)
        self.allowed = allowed_branches(importer)
        from apps.branch.models import Branch

        self.all_active_branches = {}
        for branch in Branch.objects.filter(status=Branch.STATUS_ACTIVE):
            self.all_active_branches[branch.branch_name.strip().lower()] = branch
            if branch.branch_code:
                self.all_active_branches[branch.branch_code.strip().lower()] = branch
        self.allowed_pks = {branch.pk for branch in self.allowed}
        self.seats = SeatPool(importer)
        self.existing_emails = {email.lower() for email in User.objects.values_list('email', flat=True)}
        wanted = {values.get('reporting_manager', '') for _row, values in rows if values.get('reporting_manager')}
        self.managers = {u.employee_id: u for u in User.objects.filter(employee_id__in=wanted)} if wanted else {}


def _check_branch(lookups: _Lookups, raw: str, result: RowResult) -> None:
    branch = lookups.all_active_branches.get(raw.strip().lower())
    if branch is None:
        result.errors.append(f'Company Code "{raw}" is not an active branch.')
    elif branch.pk not in lookups.allowed_pks:
        # The spreadsheet's dropdown can be edited; this is what actually enforces the importer's branch.
        own = ', '.join(b.branch_name for b in lookups.allowed) or 'none'
        result.errors.append(f'You can only import employees into your own branch ({own}). "{raw}" is not allowed for your account.')
    else:
        result.branch_name = branch.branch_name.strip()


def _check_position(lookups: _Lookups, unit: str, title: str, result: RowResult) -> None:
    """Give the row the first vacant seat of this exact org unit and title (see services_employee_import_seats)."""
    if not lookups.seats.has_org_unit(unit):
        result.errors.append(f'Org Unit "{unit}" was not found.')
        return
    allocation = lookups.seats.allocate(unit, title, result.date_of_joining, result.row)
    if allocation.error:
        result.errors.append(allocation.error)
        return
    result.position = allocation.position


def _check_manager(lookups: _Lookups, raw: str, result: RowResult) -> None:
    if not raw:
        return
    if result.position is not None and result.position.can_manage_team:
        result.errors.append('Managers do not have a reporting manager: leave Reporting Manager Employee ID blank for this position.')
        return
    manager = lookups.managers.get(raw)
    if manager is None:
        result.errors.append(f'Reporting Manager Employee ID "{raw}" does not match an existing employee.')
        return
    refusal = approver_refusal(manager, None, KIND_REPORTING_MANAGER)
    if refusal:
        result.errors.append(refusal)
        return
    if not lookups.is_admin and (manager.branch or '').strip().lower() not in {b.branch_name.strip().lower() for b in lookups.allowed}:
        result.errors.append('The reporting manager must be in your own branch.')
        return
    result.manager = manager


def _check_optional_text(values: dict, result: RowResult) -> None:
    phone = values.get('phone', '')
    if phone and not _valid_phone(phone):
        result.errors.append('Mobile Number must be a 10-digit number (optionally with +91).')
    emergency = values.get('emergency_phone', '')
    if emergency and not _valid_phone(emergency):
        result.errors.append('Emergency Contact Number must be a 10-digit number (optionally with +91).')
    personal = values.get('personal_email', '')
    if personal and not EMAIL_RE.match(personal):
        result.errors.append('Personal Email is not a valid email address.')
    gender = values.get('gender', '')
    if gender and gender.lower() not in GENDERS:
        result.errors.append('Gender must be Male, Female or Other.')
    blood = values.get('blood_group', '')
    if blood and blood.lower() not in BLOOD_GROUPS:
        result.errors.append('Blood Group must be one of A+, A-, B+, B-, O+, O-, AB+, AB-.')
    pin = values.get('pin_code', '')
    if pin and not PIN_RE.match(pin):
        result.errors.append('PIN Code must be exactly 6 digits.')
    dob = values.get('date_of_birth', '')
    if dob:
        result.date_of_birth = _iso_date(dob)
        if result.date_of_birth is None:
            result.errors.append('Date of Birth must be a real date written as YYYY-MM-DD.')
        elif result.date_of_birth >= datetime.date.today():
            result.errors.append('Date of Birth must be in the past.')


def _validate_one(lookups: _Lookups, row: int, values: dict) -> RowResult:
    result = RowResult(row=row, values=values)
    for key in REQUIRED_KEYS:
        if not values.get(key):
            header = next(column.header for column in COLUMNS if column.key == key)
            result.errors.append(f'{header} is required.')
    for key, label in (('first_name', 'First Name'), ('last_name', 'Last Name')):
        if values.get(key) and not NAME_RE.match(values[key]):
            result.errors.append(f'{label} may only contain letters, numbers, spaces, hyphens and apostrophes.')
    email = values.get('email', '')
    if email and not EMAIL_RE.match(email):
        result.errors.append('Work Email is not a valid email address.')
    if email and email.lower() in lookups.existing_emails:
        result.is_duplicate = True
        result.errors.append('Duplicate: a user with this Work Email already exists in HRMS.')
    joining = values.get('date_of_joining', '')
    if joining:
        result.date_of_joining = _iso_date(joining)
        if result.date_of_joining is None:
            result.errors.append('Date of Joining must be a real date written as YYYY-MM-DD.')
    raw_type = values.get('employee_type', '')
    if raw_type:
        canonical = normalize_employment_type(raw_type)
        if canonical is None:
            result.errors.append('Employment Type must be Permanent, Contract, Freelancer, Consultant, Part-Time, Temporary or Intern.')
        else:
            result.employee_type = canonical
    if values.get('branch'):
        _check_branch(lookups, values['branch'], result)
    if values.get('org_unit') and values.get('position'):
        _check_position(lookups, values['org_unit'], values['position'], result)
    _check_manager(lookups, values.get('reporting_manager', ''), result)
    _check_optional_text(values, result)
    return result


def _mark_in_file_duplicates(results: list[RowResult]) -> None:
    first_by_email: dict[str, int] = {}
    first_by_phone: dict[str, int] = {}
    first_by_identity: dict[tuple, int] = {}
    first_by_seat: dict = {}
    for result in results:
        if result.position is not None:
            if result.position.pk in first_by_seat:
                result.errors.append(f'The same position is used in row {first_by_seat[result.position.pk]}. A seat holds one employee.')
            else:
                first_by_seat[result.position.pk] = result.row
        email = result.values.get('email', '').lower()
        if email:
            if email in first_by_email:
                result.is_duplicate = True
                result.errors.append(f'Duplicate: the same Work Email appears in row {first_by_email[email]}.')
            else:
                first_by_email[email] = result.row
        phone = _PHONE_FORMATTING_RE.sub('', result.values.get('phone', ''))[-10:]
        if phone and len(phone) == 10:
            if phone in first_by_phone:
                result.is_duplicate = True
                result.errors.append(f'Duplicate: the same Mobile Number appears in row {first_by_phone[phone]}.')
            else:
                first_by_phone[phone] = result.row
        identity = (result.values.get('first_name', '').lower(), result.values.get('last_name', '').lower(), result.values.get('date_of_birth', ''))
        if all(identity):
            if identity in first_by_identity:
                result.is_duplicate = True
                result.errors.append(f'Duplicate: the same person (name and date of birth) appears in row {first_by_identity[identity]}.')
            else:
                first_by_identity[identity] = result.row


def validate_rows(importer: User, parsed: ParsedFile) -> list[RowResult]:
    """Check every row. Reads the database, writes nothing."""
    lookups = _Lookups(importer, parsed.rows)
    results = [_validate_one(lookups, row, values) for row, values in parsed.rows]
    _mark_in_file_duplicates(results)
    return results


@dataclass
class Summary:
    total: int
    valid: int
    invalid: int
    duplicate: int

    @property
    def can_import(self) -> bool:
        return self.total > 0 and self.invalid == 0


def summarise(results: list[RowResult]) -> Summary:
    valid = sum(1 for r in results if r.is_valid)
    return Summary(total=len(results), valid=valid, invalid=len(results) - valid, duplicate=sum(1 for r in results if r.is_duplicate))
