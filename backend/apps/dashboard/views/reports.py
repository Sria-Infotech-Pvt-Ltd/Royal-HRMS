"""
Reports screen API.

  GET  /dashboard/reports/                    the reports the signed-in person may run, with their filters;
  GET  /dashboard/reports/<key>/download/     the report as a CSV file (built on the server, in the person's own scope);
  GET  /dashboard/reports/<key>/preview/      the first rows and the row count, so they can check before sending;
  GET  /dashboard/reports/recipients/?q=      active employees to send to (name, employee id, designation; never an email);
  POST /dashboard/reports/<key>/send/         email the report to chosen active employees.

Each report needs the permission of the module it reports on (see services_reports); this screen adds no access.
"""
from __future__ import annotations

from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.dashboard.services_report_delivery import (
    MAX_NOTE_LENGTH, MAX_RECIPIENTS, DeliveryRefused, email_report, filename_for, render_csv,
)
from apps.dashboard.services_reports import MAX_ROWS, build_report, get_report, reports_for
from core.permissions import HasCompletedOnboardingStatus, has_perm
from core.responses import error, get_client_ip, success

PREVIEW_ROWS = 10
_DENIED = 'You do not have permission to run this report.'


def _catalog_entry(spec) -> dict:
    return {
        'key': spec.key, 'title': spec.title, 'description': spec.description,
        'filters': [{'key': f.key, 'label': f.label, 'kind': f.kind, 'default': f.default,
                     'options': [{'value': value, 'label': label} for value, label in f.options]} for f in spec.filters],
        'email_omits': list(spec.sensitive_columns),
    }


def _spec_for(request, key: str):
    spec = get_report(key)
    if spec is None:
        return None, error('Report not found.', http_status=status.HTTP_404_NOT_FOUND)
    if not has_perm(request.user, spec.permission):
        return None, error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
    return spec, None


class ReportCatalogView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request):
        return success('Reports retrieved.', data={
            'reports': [_catalog_entry(spec) for spec in reports_for(request.user)],
            'limits': {'max_recipients': MAX_RECIPIENTS, 'max_note_length': MAX_NOTE_LENGTH, 'max_rows': MAX_ROWS},
        })


class ReportRecipientSearchView(APIView):
    """Who a report can be emailed to: active employees only. Needs at least one report permission; reveals no contact details."""
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request):
        if not reports_for(request.user):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        term = (request.query_params.get('q') or '').strip()
        if len(term) < 2:
            return success('Type at least two characters.', data={'results': []})
        people = (User.objects.filter(is_active=True).exclude(employee_id='').exclude(email='').exclude(pk=request.user.pk)
                  .filter(Q(full_name__icontains=term) | Q(employee_id__icontains=term)).order_by('full_name')[:10])
        return success('Employees retrieved.', data={'results': [
            {'id': str(person.pk), 'employee_id': person.employee_id, 'name': person.full_name or person.email, 'designation': person.designation}
            for person in people]})


class ReportPreviewView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request, key: str):
        spec, refusal = _spec_for(request, key)
        if refusal:
            return refusal
        data = build_report(request.user, spec, request.query_params.dict())
        return success('Report preview retrieved.', data={'headers': data.headers, 'rows': data.rows[:PREVIEW_ROWS], 'row_count': len(data.rows)})


class ReportDownloadView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request, key: str):
        spec, refusal = _spec_for(request, key)
        if refusal:
            return refusal
        data = build_report(request.user, spec, request.query_params.dict())
        response = HttpResponse(render_csv(data), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename_for(spec)}"'
        return response


class ReportSendView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def post(self, request, key: str):
        spec, refusal = _spec_for(request, key)
        if refusal:
            return refusal
        body = request.data if isinstance(request.data, dict) else {}
        try:
            outcome = email_report(request.user, spec, body.get('filters') or {}, body.get('recipients'), str(body.get('note') or ''),
                                   get_client_ip(request))
        except DeliveryRefused as exc:
            return error(exc.message, http_status=exc.http_status)
        data = {'sent': len(outcome.sent), 'failed': len(outcome.failed), 'rows': outcome.row_count}
        if not outcome.sent:
            return error('The email could not be sent. Check the email (SMTP) settings and try again.', data=data,
                         http_status=status.HTTP_502_BAD_GATEWAY)
        message = f'Report emailed to {len(outcome.sent)} {"person" if len(outcome.sent) == 1 else "people"}.'
        if outcome.failed:
            message += f' {len(outcome.failed)} could not be reached.'
        return success(message, data=data)
