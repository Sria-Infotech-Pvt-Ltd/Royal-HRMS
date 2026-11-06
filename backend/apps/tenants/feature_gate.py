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
    MODULE_SEPARATION, MODULE_VOICE_COMMANDS, MODULE_DOCUMENTS, MODULE_ASSETS, MODULE_WFH,
)

# Order matters — more specific prefixes must come before broader ones
# (e.g. face-attendance sub-paths before the general attendance prefix).
MODULE_URL_PREFIXES = (
    # Dashboard endpoints that serve one module's data only (the mixed
    # dashboard endpoints filter per module inside their views instead).
    ('/api/dashboard/hr/recruitment-funnel',      MODULE_RECRUITMENT),
    ('/api/dashboard/hr/attendance-summary',      MODULE_ATTENDANCE),
    ('/api/dashboard/employee/attendance-',       MODULE_ATTENDANCE),
    ('/api/dashboard/employee/leave-balances',    MODULE_LEAVE),
    ('/api/dashboard/announcement',               MODULE_ANNOUNCEMENTS),
    ('/api/dashboard/system-admin/announcement',  MODULE_ANNOUNCEMENTS),
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


# Modules added with SaaS plans (apps.tenants.modules.LATE_GATED_MODULES).
# Existing companies had these features ungated, so these prefixes are only
# enforced when settings.SUBSCRIPTION_ENFORCEMENT == 'on' (logged in
# 'shadow'), after every company has been backfilled with the keys.
LATE_MODULE_URL_PREFIXES = (
    ('/api/documents/',        MODULE_DOCUMENTS),
    ('/api/company-contacts/', MODULE_DOCUMENTS),
    ('/api/assets/',           MODULE_ASSETS),
    ('/api/wfh/',              MODULE_WFH),
)


def resolve_late_module_for_path(path: str) -> str | None:
    for prefix, module in LATE_MODULE_URL_PREFIXES:
        if path.startswith(prefix):
            return module
    return None
