"""Profile fields an employee can ask to change with a new value, and that HR / the System Admin can then approve and apply in one step.

Fields not listed here (bank and statutory details, family and nominees, the login email, "Other") stay plain HR Help tickets that HR
handles by hand. The labels must match backend/apps/hrms/profile_correction_fields.py and the frontend profileCorrectionFields.ts.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.accounts.models import EmployeeProfile

KIND_TEXT = 'text'
KIND_DATE = 'date'
KIND_PHONE = 'phone'
KIND_PIN = 'pin'
KIND_CHOICE = 'choice'

TARGET_USER = 'user'
TARGET_PROFILE = 'profile'


@dataclass(frozen=True)
class ChangeField:
    key: str
    section: str
    label: str
    target: str
    attr: str
    kind: str = KIND_TEXT
    max_length: int = 150
    choices: tuple[tuple[str, str], ...] = ()
    # Needs a System Admin (superuser / settings.edit), like the joining date, which feeds attendance and payroll.
    full_access_only: bool = False


def _choices(field_name: str) -> tuple[tuple[str, str], ...]:
    return tuple((value, label) for value, label in EmployeeProfile._meta.get_field(field_name).choices)


def _profile(key: str, section: str, label: str, attr: str | None = None, **extra) -> ChangeField:
    return ChangeField(key=key, section=section, label=label, target=TARGET_PROFILE, attr=attr or key, **extra)


PERSONAL = 'Personal details'
CONTACT = 'Contact & address'
EMERGENCY = 'Emergency contact'

CHANGE_FIELDS: tuple[ChangeField, ...] = (
    ChangeField('full_name', PERSONAL, 'Full name', TARGET_USER, 'full_name'),
    _profile('middle_name', PERSONAL, 'Middle name', max_length=100),
    _profile('display_name', PERSONAL, 'Display name'),
    _profile('date_of_birth', PERSONAL, 'Date of birth', kind=KIND_DATE),
    _profile('place_of_birth', PERSONAL, 'Place of birth'),
    _profile('gender', PERSONAL, 'Gender', kind=KIND_CHOICE, choices=_choices('gender')),
    _profile('marital_status', PERSONAL, 'Marital status', kind=KIND_CHOICE, choices=_choices('marital_status')),
    _profile('nationality', PERSONAL, 'Nationality', max_length=100),
    _profile('father_name', PERSONAL, "Father's name"),
    _profile('mother_name', PERSONAL, "Mother's name"),
    _profile('blood_group', PERSONAL, 'Blood group', kind=KIND_CHOICE, choices=_choices('blood_group')),
    _profile('languages_known', PERSONAL, 'Languages known', max_length=255),
    ChangeField('date_of_joining', PERSONAL, 'Date of joining', TARGET_USER, 'date_of_joining', kind=KIND_DATE, full_access_only=True),
    ChangeField('phone', CONTACT, 'Mobile number', TARGET_USER, 'phone', kind=KIND_PHONE, max_length=20),
    _profile('current_address', CONTACT, 'Current address', max_length=500),
    _profile('current_village', CONTACT, 'Current village / town'),
    _profile('current_district', CONTACT, 'Current district', max_length=100),
    _profile('current_state', CONTACT, 'Current state', max_length=100),
    _profile('current_pin_code', CONTACT, 'Current PIN code', kind=KIND_PIN, max_length=6),
    _profile('permanent_address', CONTACT, 'Permanent address', max_length=500),
    _profile('permanent_village', CONTACT, 'Permanent village / town'),
    _profile('permanent_district', CONTACT, 'Permanent district', max_length=100),
    _profile('permanent_state', CONTACT, 'Permanent state', max_length=100),
    _profile('permanent_pin_code', CONTACT, 'Permanent PIN code', kind=KIND_PIN, max_length=6),
    _profile('emergency_name', EMERGENCY, 'Emergency contact name'),
    _profile('emergency_relationship', EMERGENCY, 'Emergency contact relationship', max_length=50),
    _profile('emergency_phone', EMERGENCY, 'Emergency contact phone', kind=KIND_PHONE, max_length=20),
    _profile('emergency_email', EMERGENCY, 'Emergency contact email', max_length=254),
)

_BY_KEY = {spec.key: spec for spec in CHANGE_FIELDS}
_BY_LABEL = {(spec.section, spec.label): spec for spec in CHANGE_FIELDS}


def spec_for_key(key: str) -> ChangeField | None:
    return _BY_KEY.get(key)


def spec_for_label(section: str, label: str) -> ChangeField | None:
    return _BY_LABEL.get((section, label))


def public_registry() -> list[dict]:
    """What the frontend needs to draw the right input for each field."""
    return [
        {
            'key': spec.key, 'section': spec.section, 'label': spec.label, 'kind': spec.kind, 'max_length': spec.max_length,
            'choices': [{'value': value, 'label': label} for value, label in spec.choices],
            'full_access_only': spec.full_access_only,
        }
        for spec in CHANGE_FIELDS
    ]
