"""
Getting a report to people: a download for the person who ran it, or an email to chosen colleagues.

Rules for the email:
  - the report is built here, on the server, for the sender (never from anything the browser supplies);
  - recipients must be active employees with an email on file, picked by id, at most MAX_RECIPIENTS; nobody outside the
    employee directory can be addressed;
  - contact-detail columns (spec.sensitive_columns) are left out of the emailed copy;
  - each recipient gets their own message, so recipients do not see each other;
  - a sender may send MAX_SENDS_PER_HOUR emails; every send is written to the audit log (who, which report, filters, how
    many recipients and rows, never the data itself).
"""
from __future__ import annotations

import csv
import datetime
import io
import logging
from dataclasses import dataclass, field

from django.core.cache import cache

from apps.accounts.models import AuditLog, Company, User
from apps.accounts.utils import send_template_email
from apps.dashboard.services_reports import ReportData, ReportSpec, build_report, clean_params

logger = logging.getLogger(__name__)

MAX_RECIPIENTS = 20
MAX_SENDS_PER_HOUR = 10
MAX_EMAIL_ROWS = 5000
MAX_NOTE_LENGTH = 1000
TEMPLATE = 'report_shared'


class DeliveryRefused(Exception):
    """The report cannot be sent; `message` is safe to show the sender."""

    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.message, self.http_status = message, http_status


def _safe_cell(value) -> str:
    """Stops a cell from being run as a spreadsheet formula (CSV injection) when the file is opened in Excel."""
    text = '' if value is None else str(value)
    return "'" + text if text[:1] in ('=', '+', '-', '@', '\t', '\r') else text


def render_csv(data: ReportData) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow([_safe_cell(header) for header in data.headers])
    for row in data.rows:
        writer.writerow([_safe_cell(cell) for cell in row])
    return b'\xef\xbb\xbf' + buffer.getvalue().encode('utf-8')       # BOM so Excel reads it as UTF-8


def filename_for(spec: ReportSpec) -> str:
    return f'{spec.key}-report-{datetime.date.today().isoformat()}.csv'


def _recipients(ids) -> list[User]:
    if not isinstance(ids, list) or not ids:
        raise DeliveryRefused('Choose at least one recipient.')
    unique = list(dict.fromkeys(str(item) for item in ids))
    if len(unique) > MAX_RECIPIENTS:
        raise DeliveryRefused(f'You can send a report to at most {MAX_RECIPIENTS} people at a time.')
    try:
        found = list(User.objects.filter(pk__in=unique, is_active=True).exclude(employee_id='').exclude(email=''))
    except Exception:                                                  # malformed ids
        raise DeliveryRefused('One of the recipients is not valid.')
    if len(found) != len(unique):
        raise DeliveryRefused('Reports can only be sent to active employees. One or more recipients are not.')
    return found


def _check_rate(sender: User) -> None:
    key = f'report_sends:{sender.pk}'
    used = cache.get(key, 0)
    if used >= MAX_SENDS_PER_HOUR:
        raise DeliveryRefused(f'You have reached the limit of {MAX_SENDS_PER_HOUR} report emails per hour. Try again later.', 429)
    cache.set(key, used + 1, 3600)


@dataclass
class SendOutcome:
    sent: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    row_count: int = 0


def email_report(sender: User, spec: ReportSpec, raw_params: dict, recipient_ids, note: str, ip_address: str | None) -> SendOutcome:
    people = _recipients(recipient_ids)
    note = (note or '').strip()[:MAX_NOTE_LENGTH]
    data = build_report(sender, spec, raw_params).without_columns(spec.sensitive_columns)
    if not data.rows:
        raise DeliveryRefused('This report has no rows for the chosen filters, so there is nothing to send.')
    if len(data.rows) > MAX_EMAIL_ROWS:
        raise DeliveryRefused(f'This report has more than {MAX_EMAIL_ROWS} rows. Narrow the filters, or download it instead.')
    _check_rate(sender)

    attachment = (filename_for(spec), render_csv(data), 'text/csv')
    company = Company.objects.first()
    outcome = SendOutcome(row_count=len(data.rows))
    for person in people:
        try:
            send_template_email(
                recipient_email=person.email, template_name=TEMPLATE, module='dashboard', triggered_by=sender, reply_to=sender.email or None,
                context={
                    'recipient_name': person.full_name or person.email, 'sender_name': sender.full_name or sender.email,
                    'report_title': spec.title, 'row_count': str(outcome.row_count), 'note': note or 'No additional note.',
                    'generated_on': datetime.date.today().strftime('%d %b %Y'), 'company_name': company.company_name if company else '',
                },
                extra_attachments=[attachment],
            )
            outcome.sent.append(str(person.pk))
        except Exception:
            logger.exception('Report email to employee %s failed', person.pk)
            outcome.failed.append(str(person.pk))
    AuditLog.objects.create(
        user=sender, action='report_emailed', module='dashboard', object_id=spec.key, ip_address=ip_address,
        changes={'report': spec.key, 'filters': {k: str(v) for k, v in clean_params(spec, raw_params).items()},
                 'recipients': len(people), 'sent': len(outcome.sent), 'failed': len(outcome.failed), 'rows': outcome.row_count},
    )
    return outcome
