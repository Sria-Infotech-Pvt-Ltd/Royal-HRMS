"""
Weekly timesheet endpoints (base: /api/attendance/timesheets/). Views only read the request, call the service and shape the
response; every rule lives in the services.

  GET  my/?week=YYYY-MM-DD        the week's sheet (or a prefilled draft); without ?week, the employee's own history (paginated)
  PUT  my/<week>/                 save a draft (the Monday of the week)
  POST my/<week>/submit/          submit or resubmit
  GET  team/?status=&week=        the approver's queue (paginated)
  GET  <id>/                      one sheet, read-only, with its history
  POST <id>/approve/              approve (the assigned approver, or HR in scope)
  POST <id>/return/               send back; {"reason": ...} required
  POST <id>/unlock/               HR reopens an approved sheet; {"reason": ...} required

Looking at another employee's workspace uses the global read-only view-as header (see apps.accounts.authentication), so GETs
here show that employee and every write is refused there; no employee id is accepted by these views.
"""
from __future__ import annotations

import datetime

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.attendance import services_timesheet as employee_actions
from apps.attendance import services_timesheet_decisions as decisions
from apps.attendance.serializers_timesheet import ReasonSerializer, TeamListQuerySerializer, WeekQuerySerializer
from apps.attendance.services_timesheet_access import team_queryset
from apps.attendance.services_timesheet_common import (
    TimesheetConflict, TimesheetError, TimesheetForbidden, TimesheetNotFound, monday_of,
)
from apps.attendance.services_timesheet_lists import my_history, pending_count, sheet_row, team_rows
from core.pagination import paginate, paginated_data
from core.permissions import HasCompletedOnboardingStatus
from core.responses import error, first_error, get_client_ip, success

_HTTP_FOR = {TimesheetNotFound: 404, TimesheetConflict: 409, TimesheetForbidden: 403}


def _failure(exc: TimesheetError) -> Response:
    http_status = next((code for kind, code in _HTTP_FOR.items() if isinstance(exc, kind)), status.HTTP_400_BAD_REQUEST)
    return error(exc.message, data={'errors': exc.errors, 'code': exc.code}, http_status=http_status)


def _week(raw: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        raise TimesheetError('The week must be a date like 2026-11-09.') from None


class _TimesheetView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]


class MyTimesheetView(_TimesheetView):
    def get(self, request: Request) -> Response:
        if 'week' in request.query_params:
            query = WeekQuerySerializer(data=request.query_params)
            if not query.is_valid():
                return error(first_error(query.errors), data=query.errors, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            return success('Timesheet retrieved.', employee_actions.get_week(request.user, query.validated_data['week']))
        page, paginator = paginate(my_history(request.user), request, default_page_size=20)
        rows = [sheet_row(sheet) for sheet in page.object_list]
        return success('Timesheets retrieved.', paginated_data(paginator, page, rows))


class MyTimesheetWeekView(_TimesheetView):
    def put(self, request: Request, week: str) -> Response:
        try:
            data = employee_actions.save_draft(request.user, _week(week), request.data, actor=request.user)
        except TimesheetError as exc:
            return _failure(exc)
        return success('Timesheet saved.', data)


class MyTimesheetSubmitView(_TimesheetView):
    def post(self, request: Request, week: str) -> Response:
        try:
            data = employee_actions.submit(request.user, _week(week), actor=request.user, ip_address=get_client_ip(request))
        except TimesheetError as exc:
            return _failure(exc)
        return success('Timesheet submitted for approval.', data)


class TeamTimesheetListView(_TimesheetView):
    def get(self, request: Request) -> Response:
        query = TeamListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return error(first_error(query.errors), data=query.errors, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        params = query.validated_data
        week = params.get('week')
        queryset = team_queryset(request.user, status=params.get('status', ''), week_start=monday_of(week) if week else None)
        page, paginator = paginate(queryset, request, default_page_size=20)
        data = paginated_data(paginator, page, team_rows(list(page.object_list)))
        data['pending_count'] = pending_count(request.user)
        return success('Team timesheets retrieved.', data)


class TimesheetDetailView(_TimesheetView):
    def get(self, request: Request, pk) -> Response:
        try:
            sheet = decisions.load_sheet_by_id(pk)
            return success('Timesheet retrieved.', decisions.detail_for(request.user, sheet))
        except TimesheetError as exc:
            return _failure(exc)


class _DecisionView(_TimesheetView):
    needs_reason = True
    message = ''

    def run(self, request: Request, pk, reason: str):
        raise NotImplementedError

    def post(self, request: Request, pk) -> Response:
        reason = ''
        if self.needs_reason:
            body = ReasonSerializer(data=request.data)
            if not body.is_valid():
                return error(first_error(body.errors), data=body.errors)
            reason = body.validated_data['reason']
        try:
            return success(self.message, self.run(request, pk, reason))
        except TimesheetError as exc:
            return _failure(exc)


class TimesheetApproveView(_DecisionView):
    needs_reason = False
    message = 'Timesheet approved.'

    def run(self, request, pk, reason):
        return decisions.approve(pk, request.user, ip_address=get_client_ip(request))


class TimesheetReturnView(_DecisionView):
    message = 'Timesheet sent back to the employee.'

    def run(self, request, pk, reason):
        return decisions.return_to_employee(pk, request.user, reason, ip_address=get_client_ip(request))


class TimesheetUnlockView(_DecisionView):
    message = 'Timesheet reopened for correction.'

    def run(self, request, pk, reason):
        return decisions.unlock(pk, request.user, reason, ip_address=get_client_ip(request))
