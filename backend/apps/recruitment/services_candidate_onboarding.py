"""
Sending a selected candidate their onboarding link (HR-led recruitment path).

HR stays the candidate's direct contact: the link email is sent on HR's behalf with Reply-To set to the acting HR user and
their name and email shown in the message, and the same HR user is recorded as the candidate's HR contact (User.hr) so the
candidate portal can show who to write to.

No password is created, emailed or reset here and no employee account is activated: see
apps.accounts.services_onboarding_link for the link itself.
"""
from __future__ import annotations

import logging

from apps.accounts.models import AuditLog, Company, PasswordResetToken
from apps.accounts.services_onboarding_link import expiry_label, issue_onboarding_link
from apps.accounts.utils import send_template_email
from apps.recruitment.models import CandidateEmail, CandidateLog

logger = logging.getLogger(__name__)
TEMPLATE = 'candidate_onboarding_link'


def hr_contact_of(actor) -> tuple[str, str] | None:
    return ((actor.full_name or actor.email), actor.email) if actor is not None and actor.email else None


def close_candidate_access(candidate) -> bool:
    """Shut the candidate's onboarding access when HR rejects them: any unopened link stops working and the limited session
    (and login) is deactivated. Does nothing once the onboarding is approved: by then it is an employee's account."""
    portal_user = candidate.portal_user
    if portal_user is None or not portal_user.requires_self_service_onboarding:
        return False
    if portal_user.onboarding_status == portal_user.ONBOARDING_COMPLETE:
        return False
    PasswordResetToken.objects.filter(user=portal_user, is_used=False).update(is_used=True)
    if portal_user.is_active:
        portal_user.is_active = False
        portal_user.save(update_fields=['is_active', 'updated_at'])
    return True


def send_onboarding_link(candidate, portal_user, actor, *, ip_address: str | None = None, resend: bool = False) -> bool:
    """Issue a fresh one-time link for `portal_user` and email it. Returns True when the email left the server."""
    portal_user.hr = actor
    portal_user.save(update_fields=['hr', 'updated_at'])
    token, url = issue_onboarding_link(portal_user)
    company = Company.objects.first()
    company_name = company.company_name if company else ''
    sent = False
    try:
        send_template_email(
            recipient_email=candidate.email, template_name=TEMPLATE, module='recruitment', triggered_by=actor,
            context={'candidate_name': candidate.name, 'position': candidate.position_applied, 'company_name': company_name,
                     'onboarding_link': url, 'expires_on': expiry_label(token)},
            reply_to=actor.email or None, hr_contact=hr_contact_of(actor),
        )
        sent = True
    except Exception:
        logger.exception('Failed to send the onboarding link to %s', candidate.email)
    CandidateEmail.objects.create(
        candidate=candidate, template_used=TEMPLATE, to_email=candidate.email, sent_by=actor,
        subject=f'Complete your onboarding — {company_name}' + (' (resent)' if resend else ''),
        status=CandidateEmail.STATUS_SENT if sent else CandidateEmail.STATUS_FAILED,
    )
    who = actor.full_name or actor.email
    if sent:
        title = 'Onboarding link resent' if resend else 'Onboarding link sent'
    else:
        title = 'Onboarding link email failed: check SMTP settings'
    CandidateLog.objects.create(
        candidate=candidate, log_type=CandidateLog.TYPE_SUCCESS if sent else CandidateLog.TYPE_WARN, title=title,
        description=f'To {candidate.email}, by {who}. One-time link, expires {expiry_label(token)}. No account is activated until HR approves.',
    )
    AuditLog.objects.create(
        user=actor, action='onboarding_link_resent' if resend else 'onboarding_link_sent', module='recruitment',
        object_id=str(candidate.pk), changes={'email': candidate.email, 'delivered': sent},
        branch=candidate.branch.branch_name if candidate.branch else '', ip_address=ip_address,
    )
    return sent
