"""
SaaS feature catalogue — what a subscription plan can include.

Built on the existing module switches (apps.tenants.models.ALL_MODULES /
Client.enabled_modules); this file only describes how each sellable feature
maps onto them. Kinds:

  core         always on, cannot be switched off (no module key)
  module       a real, switchable, backend-enforced module key
  display      shown on plans / pricing, no switch (e.g. Priority support)
  coming_soon  not built yet — shown as "Coming soon", cannot be included

`depends_on` lists module keys a module needs; resolve_modules() adds them.
"""
from __future__ import annotations

from apps.tenants.models import (
    MODULE_ANNOUNCEMENTS, MODULE_ASSESSMENTS, MODULE_ASSETS, MODULE_ATTENDANCE, MODULE_DOCUMENTS,
    MODULE_EXPENSES, MODULE_FACE_ATTENDANCE, MODULE_LEAVE, MODULE_PAYROLL, MODULE_RECRUITMENT,
    MODULE_SEPARATION, MODULE_VOICE_COMMANDS, MODULE_WFH,
)

CORE, MODULE, DISPLAY, COMING_SOON = 'core', 'module', 'display', 'coming_soon'

FEATURES: list[dict] = [
    # ── Core: always included ──
    {'key': 'employee_management', 'label': 'Employee Management', 'category': 'Core HR', 'kind': CORE},
    {'key': 'self_service', 'label': 'Employee Self-Service', 'category': 'Core HR', 'kind': CORE},
    {'key': 'onboarding', 'label': 'Employee Onboarding', 'category': 'Core HR', 'kind': CORE},
    {'key': 'approval_workflows', 'label': 'Approval Workflows', 'category': 'Core HR', 'kind': CORE},
    {'key': 'roles_permissions', 'label': 'Roles & Permissions', 'category': 'Core HR', 'kind': CORE},
    {'key': 'notifications', 'label': 'Notifications', 'category': 'Core HR', 'kind': CORE},
    # ── Switchable modules (backend-enforced) ──
    {'key': MODULE_ATTENDANCE, 'label': 'Attendance', 'category': 'Time', 'kind': MODULE},
    {'key': MODULE_FACE_ATTENDANCE, 'label': 'Face ID Attendance', 'category': 'Time', 'kind': MODULE,
     'depends_on': [MODULE_ATTENDANCE]},
    {'key': MODULE_LEAVE, 'label': 'Leave Management & Holiday Calendar', 'category': 'Time', 'kind': MODULE},
    {'key': MODULE_WFH, 'label': 'Work From Home', 'category': 'Time', 'kind': MODULE},
    {'key': MODULE_PAYROLL, 'label': 'Payroll, Salary Structures, Payslips, PF / ESI / PT', 'category': 'Payroll',
     'kind': MODULE, 'depends_on': [MODULE_ATTENDANCE, MODULE_LEAVE]},
    {'key': MODULE_EXPENSES, 'label': 'Expense & Reimbursement', 'category': 'Payroll', 'kind': MODULE},
    {'key': MODULE_RECRUITMENT, 'label': 'Recruitment & Applicant Tracking', 'category': 'Talent', 'kind': MODULE},
    {'key': MODULE_ASSESSMENTS, 'label': 'Assessments', 'category': 'Talent', 'kind': MODULE},
    {'key': MODULE_SEPARATION, 'label': 'Exit Management (Separation)', 'category': 'Core HR', 'kind': MODULE},
    {'key': MODULE_DOCUMENTS, 'label': 'Document Management', 'category': 'Core HR', 'kind': MODULE},
    {'key': MODULE_ASSETS, 'label': 'Asset Management', 'category': 'Operations', 'kind': MODULE},
    {'key': MODULE_ANNOUNCEMENTS, 'label': 'Announcements', 'category': 'Engagement', 'kind': MODULE},
    {'key': MODULE_VOICE_COMMANDS, 'label': 'Voice Commands', 'category': 'Engagement', 'kind': MODULE},
    # ── Display only (no switch) ──
    {'key': 'mobile_access', 'label': 'Mobile-friendly Access', 'category': 'Platform', 'kind': DISPLAY},
    {'key': 'basic_reports', 'label': 'Basic HR Reports (module exports)', 'category': 'Reports', 'kind': DISPLAY},
    {'key': 'advanced_dashboards', 'label': 'Advanced Dashboards', 'category': 'Reports', 'kind': DISPLAY},
    {'key': 'multi_branch', 'label': 'Multi-Branch & Multi-Location', 'category': 'Platform', 'kind': DISPLAY},
    {'key': 'advanced_rbac', 'label': 'Advanced Role-Based Access', 'category': 'Platform', 'kind': DISPLAY},
    {'key': 'priority_support', 'label': 'Priority Support', 'category': 'Platform', 'kind': DISPLAY},
    # ── Not built yet ──
    {'key': 'tds', 'label': 'TDS Workflows', 'category': 'Payroll', 'kind': COMING_SOON},
    {'key': 'performance', 'label': 'Performance Management', 'category': 'Talent', 'kind': COMING_SOON},
    {'key': 'appraisal', 'label': 'Appraisal Cycles', 'category': 'Talent', 'kind': COMING_SOON},
    {'key': 'training', 'label': 'Training & Learning', 'category': 'Talent', 'kind': COMING_SOON},
    {'key': 'advanced_reports', 'label': 'Advanced Reports', 'category': 'Reports', 'kind': COMING_SOON},
    {'key': 'hr_analytics', 'label': 'Advanced HR Analytics', 'category': 'Reports', 'kind': COMING_SOON},
    {'key': 'roster', 'label': 'Shift Roster Planning', 'category': 'Time', 'kind': COMING_SOON},
    {'key': 'legal_entities', 'label': 'Multiple Legal Entities', 'category': 'Platform', 'kind': COMING_SOON},
    {'key': 'api_integrations', 'label': 'API Integrations', 'category': 'Platform', 'kind': COMING_SOON},
    {'key': 'custom_workflows', 'label': 'Custom Workflows', 'category': 'Platform', 'kind': COMING_SOON},
]

FEATURES_BY_KEY = {f['key']: f for f in FEATURES}
MODULE_FEATURES = {f['key'] for f in FEATURES if f['kind'] == MODULE}
SELECTABLE_FEATURES = {f['key'] for f in FEATURES if f['kind'] in (MODULE, DISPLAY)}
CORE_FEATURES = [f['key'] for f in FEATURES if f['kind'] == CORE]

# Module keys added after companies already existed: they had these features
# ungated, so their URL gates apply only under SUBSCRIPTION_ENFORCEMENT=on
# (after every company has been backfilled with them — see
# `manage.py assign_legacy_subscriptions`).
LATE_GATED_MODULES = (MODULE_DOCUMENTS, MODULE_ASSETS, MODULE_WFH)


def validate_features(keys) -> tuple[list[str], list[str]]:
    """(clean sorted feature keys, errors) for a plan's feature list."""
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        return [], ['Features must be a list of feature keys.']
    errors = []
    for k in keys:
        f = FEATURES_BY_KEY.get(k)
        if f is None:
            errors.append(f'Unknown feature "{k}".')
        elif f['kind'] == COMING_SOON:
            errors.append(f'"{f["label"]}" is not available yet and cannot be included.')
        elif f['kind'] == CORE:
            errors.append(f'"{f["label"]}" is always included.')
    return sorted(set(k for k in keys if k in SELECTABLE_FEATURES)), errors


def with_dependencies(modules) -> list[str]:
    """Module keys plus everything they depend on (transitively)."""
    out = set(modules)
    changed = True
    while changed:
        changed = False
        for key in list(out):
            for dep in FEATURES_BY_KEY.get(key, {}).get('depends_on', []):
                if dep not in out:
                    out.add(dep)
                    changed = True
    return sorted(out)


def resolve_modules(features, extra_modules=(), removed_modules=()) -> list[str]:
    """Enabled module keys for a subscription: the plan's module features,
    plus approved extras, minus approved removals, plus dependencies of what
    remains. (A dependency still needed by a remaining module stays on.)"""
    modules = {k for k in features if k in MODULE_FEATURES}
    modules |= {k for k in extra_modules if k in MODULE_FEATURES}
    modules -= set(removed_modules)
    return with_dependencies(modules)


def catalogue() -> list[dict]:
    return [{'key': f['key'], 'label': f['label'], 'category': f['category'], 'kind': f['kind'],
             'depends_on': f.get('depends_on', [])} for f in FEATURES]
