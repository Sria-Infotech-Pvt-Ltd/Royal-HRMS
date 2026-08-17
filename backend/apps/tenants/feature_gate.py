"""
Module on/off enforcement per company (spec: "if one company wants 5
functionalities and another wants 7, we can give them what they want").

Maps URL path prefixes to the module keys in apps.tenants.models.ALL_MODULES
and blocks the request with a 403 if the current tenant hasn't enabled that
module — checked once, centrally, rather than requiring every view across
every app to remember a module-specific permission class.

Deliberately NOT gated: auth/profile/employee-core endpoints (api/, minus
the specific sub-paths below), branch, notifications, dashboard, admin —
these are core plumbing every company needs regardless of which optional
modules they've bought.
"""
from apps.tenants.models import (
    MODULE_ANNOUNCEMENTS, MODULE_ASSESSMENTS, MODULE_ATTENDANCE, MODULE_EXPENSES,
    MODULE_FACE_ATTENDANCE, MODULE_LEAVE, MODULE_PAYROLL, MODULE_RECRUITMENT,
    MODULE_SEPARATION, MODULE_VOICE_COMMANDS,
)

# Order matters — more specific prefixes must come before broader ones
# (e.g. face-attendance sub-paths before the general attendance prefix).
MODULE_URL_PREFIXES = (
    ('/api/attendance/face', MODULE_FACE_ATTENDANCE),
    ('/api/attendance/',     MODULE_ATTENDANCE),
    ('/api/announcements/',  MODULE_ANNOUNCEMENTS),
    ('/api/recruitment/',    MODULE_RECRUITMENT),
    ('/api/leave/',          MODULE_LEAVE),
    ('/api/expenses/',       MODULE_EXPENSES),
    ('/api/separation/',     MODULE_SEPARATION),
    ('/api/payroll/',        MODULE_PAYROLL),
    ('/api/voice/',          MODULE_VOICE_COMMANDS),
    ('/api/assessments/',    MODULE_ASSESSMENTS),
)


def resolve_module_for_path(path: str) -> str | None:
    """The module key gating this path, or None if the path isn't gated at all."""
    for prefix, module in MODULE_URL_PREFIXES:
        if path.startswith(prefix):
            return module
    return None
