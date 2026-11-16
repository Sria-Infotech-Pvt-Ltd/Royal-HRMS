"""The Section -> Field choices of a profile-correction request (HRHelpRequest, topic 'profile_correction').

Keep in sync with frontend/app/dashboard/ess/_components/profileCorrectionFields.ts: the employee picks both from fixed
dropdowns there, and the server rejects any pair that is not listed here.
"""
from __future__ import annotations

OTHER_SECTION = 'Other'
OTHER_FIELD = 'Other (describe in the reason)'

PROFILE_CORRECTION_FIELDS: dict[str, tuple[str, ...]] = {
    'Personal details': (
        'Full name', 'Salutation', 'Middle name', 'Display name', 'Date of birth', 'Place of birth', 'Gender', 'Marital status',
        'Nationality', "Father's name", "Mother's name", 'Blood group', 'Languages known',
        'Date of joining',
    ),
    'Contact & address': (
        'Mobile number', 'Personal email',
        'Current address', 'Current village / town', 'Current district', 'Current state', 'Current PIN code',
        'Permanent address', 'Permanent village / town', 'Permanent district', 'Permanent state', 'Permanent PIN code',
    ),
    'Emergency contact': (
        'Emergency contact name', 'Emergency contact relationship', 'Emergency contact phone', 'Emergency contact email',
    ),
    'Bank details': ('Bank name', 'Branch name', 'Account holder name', 'Account type', 'Account number', 'IFSC code'),
    'Family & nomination': (
        'Family member name', 'Family member relationship', 'Family member date of birth', 'Family member gender',
        'Family member blood group', 'Dependent status', 'Nominee and share percentage', 'Add or remove a family member',
    ),
    OTHER_SECTION: (OTHER_FIELD,),
}
