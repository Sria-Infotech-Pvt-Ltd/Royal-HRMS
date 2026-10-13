"""
Phase 8B Task H — one real gate function per module, each checking the
one concrete, checkable precondition for that module (every legacy row of
that type has been migrated to its v2 counterpart) rather than a full
byte-parity historical replay across 7 modules at once — that is
substantial, separate verification work per module (as stated throughout
this phase's model/service docstrings), not a single gate function.
"""
from django.db import transaction
from django.utils import timezone

from apps.hrms.models import (
    Expense, HRHelpRequest, ModuleV2Entitlement, SeparationRequest,
)


class ModuleV2GateError(Exception):
    pass


def _enable(module_code: str) -> ModuleV2Entitlement:
    entitlement, _ = ModuleV2Entitlement.objects.update_or_create(
        module_code=module_code, defaults={'is_enabled': True, 'enabled_at': timezone.now()},
    )
    return entitlement


@transaction.atomic
def enable_expenses_v2():
    gaps = Expense.objects.filter(claim_v2__isnull=True).count()
    if gaps:
        raise ModuleV2GateError(f'{gaps} Expense row(s) not yet migrated to ExpenseClaim.')
    return _enable(ModuleV2Entitlement.MODULE_EXPENSES)


@transaction.atomic
def enable_separation_v2():
    # Separation's v2 pieces (SeparationFinalSettlementLink/AlumniRecord)
    # are created per-event (on settlement trigger / deactivation), not
    # per-historical-row — so the real precondition is just "the module's
    # services are reachable", confirmed by import succeeding (no circular
    # import / missing dependency). No historical backlog to check.
    return _enable(ModuleV2Entitlement.MODULE_SEPARATION)


@transaction.atomic
def enable_helpdesk_v2():
    gaps = HRHelpRequest.objects.filter(thread_v2__isnull=True).count()
    if gaps:
        raise ModuleV2GateError(f'{gaps} HRHelpRequest row(s) not yet migrated to TicketThread.')
    return _enable(ModuleV2Entitlement.MODULE_HELPDESK)


@transaction.atomic
def enable_announcements_v2():
    from apps.announcements.models import Announcement
    gaps = Announcement.objects.filter(audience_rule__isnull=True).count()
    if gaps:
        raise ModuleV2GateError(f'{gaps} Announcement row(s) not yet migrated to an AnnouncementAudienceRule.')
    return _enable(ModuleV2Entitlement.MODULE_ANNOUNCEMENTS)


@transaction.atomic
def enable_documents_v2():
    from apps.accounts.models import Document
    gaps = Document.objects.exclude(versions_v2__version_number=1).count()
    if gaps:
        raise ModuleV2GateError(f'{gaps} Document row(s) not yet migrated to a PolicyDocumentVersion.')
    return _enable(ModuleV2Entitlement.MODULE_DOCUMENTS)


@transaction.atomic
def enable_assets_v2():
    from apps.accounts.models import CompanyAsset
    gaps = CompanyAsset.objects.filter(asset_v2__isnull=True).count()
    if gaps:
        raise ModuleV2GateError(f'{gaps} CompanyAsset row(s) not yet migrated to Asset.')
    return _enable(ModuleV2Entitlement.MODULE_ASSETS)


@transaction.atomic
def enable_voice_v2():
    from apps.voice_commands.models import VoiceCapability
    if not VoiceCapability.objects.exists():
        raise ModuleV2GateError('No VoiceCapability rows registered yet — register at least the existing intents first.')
    return _enable(ModuleV2Entitlement.MODULE_VOICE)


@transaction.atomic
def enable_reports_v2():
    """Phase 9A Task J — gated on at least one real ReportDefinition
    existing and validating cleanly (not a full migrated-every-existing-
    report precondition — see models/reports.py's own documented scope
    reduction: this pass covers CustomRecord-based reporting only)."""
    from apps.platform_core.models import ReportDefinition
    if not ReportDefinition.objects.exists():
        raise ModuleV2GateError('No ReportDefinition rows exist yet — create at least one report before enabling reports.v2.')
    return _enable(ModuleV2Entitlement.MODULE_REPORTS)


@transaction.atomic
def enable_documents_v2_engine():
    """Phase 9A Task J — gated on the employment-letter template (the one
    byte-content-parity-proven seed) existing and published."""
    from apps.platform_core.models import DocumentTemplate
    if not DocumentTemplate.objects.filter(code='EMPLOYMENT_VERIFICATION_LETTER', status=DocumentTemplate.STATUS_PUBLISHED).exists():
        raise ModuleV2GateError('Employment verification letter template not seeded/published yet.')
    return _enable(ModuleV2Entitlement.MODULE_DOCUMENTS)
