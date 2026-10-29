"""
WFH daily work report (company policy section 7).

  GET  /api/wfh/reports/?mine=1            the signed-in employee's own reports
  GET  /api/wfh/reports/                   reports the signed-in user can review
  POST /api/wfh/reports/                   submit today's (or a past day's) report
  POST /api/wfh/reports/<id>/review/       Senior / Department Head or HR decides
                                           Full Day / Half Day / Not accepted

Reviewers: the WFH request's L1 approver (the employee's Senior / reporting
manager), HR with wfh.approve who can access the request, the branch's Branch
Admin, or settings.edit — never the employee themselves. Attendance only
changes when Attendance Settings → WFH daily report rule is switched on
(see apps.attendance.services_policy.wfh_report_status).
"""
from __future__ import annotations

import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.hrms.models import REQ_APPROVED, WFHDailyReport, WorkFromHomeRequest
from apps.hrms.views.workfromhome import _branch_admin_covers, _can_hr_access_request, _is_branch_admin
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success

logger = logging.getLogger(__name__)


def _can_review(user, report: WFHDailyReport) -> bool:
    if report.employee_id == user.id:
        return False
    if _has_perm(user, 'settings.edit'):
        return True
    if _is_branch_admin(user):
        return _branch_admin_covers(user, report.employee)
    wfh = report.wfh_request
    if wfh.l1_approver_id == user.id:
        return True
    return _has_perm(user, 'wfh.approve') and _can_hr_access_request(user, wfh)


def _reprocess(report: WFHDailyReport) -> None:
    """Re-derive the day's attendance so the report outcome shows everywhere
    (attendance screens, exports, payroll) — only for days that have happened."""
    if report.date > timezone.localdate():
        return
    from apps.attendance.services_attendance import AttendanceProcessorService
    try:
        AttendanceProcessorService.process_day(report.employee, report.date)
    except Exception:
        logger.exception('Re-processing attendance after WFH report %s failed', report.pk)


class WFHDailyReportSerializer(serializers.ModelSerializer):
    employee_name    = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code    = serializers.CharField(source='employee.employee_id', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    can_review       = serializers.SerializerMethodField()

    class Meta:
        model = WFHDailyReport
        fields = ('id', 'date', 'completed_work', 'pending_work', 'updates', 'submitted_at', 'submitted_late',
                  'review_status', 'reviewed_by_name', 'reviewed_at', 'review_remarks',
                  'employee_name', 'employee_code', 'can_review')

    def get_reviewed_by_name(self, obj) -> str:
        return obj.reviewed_by.full_name if obj.reviewed_by_id else ''

    def get_can_review(self, obj) -> bool:
        request = self.context.get('request')
        return bool(request) and obj.review_status == WFHDailyReport.REVIEW_PENDING and _can_review(request.user, obj)


class WFHDailyReportSubmitSerializer(serializers.Serializer):
    date           = serializers.DateField(required=False)
    completed_work = serializers.CharField(max_length=5000)
    pending_work   = serializers.CharField(max_length=5000, required=False, allow_blank=True, default='')
    updates        = serializers.CharField(max_length=5000, required=False, allow_blank=True, default='')

    def validate_completed_work(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError('Describe the work completed.')
        return value.strip()


class WFHDailyReportListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = WFHDailyReport.objects.select_related('employee', 'reviewed_by', 'wfh_request')
        if (request.query_params.get('mine') or '').lower() in ('1', 'true', 'yes'):
            qs = qs.filter(employee=request.user)
        else:
            qs = qs.exclude(employee=request.user)
            if not _has_perm(request.user, 'settings.edit'):
                scope = Q(wfh_request__l1_approver=request.user)
                if _has_perm(request.user, 'wfh.approve') or _is_branch_admin(request.user):
                    branch = (request.user.branch or '').strip()
                    scope |= Q(employee__branch=branch) if branch else Q()
                qs = qs.filter(scope)
            status_f = request.query_params.get('status', '')
            if status_f:
                qs = qs.filter(review_status=status_f)
            # The query above narrows by branch; the per-report rule (who may
            # review it, reviewed or not) has the final say.
            qs = [r for r in qs[:500] if _can_review(request.user, r)]
        data = WFHDailyReportSerializer(list(qs)[:200], many=True, context={'request': request}).data
        return success('WFH reports.', data=data)

    def post(self, request):
        ser = WFHDailyReportSubmitSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))
        data = ser.validated_data
        today = timezone.localdate()
        day = data.get('date') or today
        if day > today:
            return error('You cannot submit a report for a future date.')
        wfh = (
            WorkFromHomeRequest.objects
            .filter(employee=request.user, status=REQ_APPROVED, start_date__lte=day, end_date__gte=day)
            .order_by('-created_at').first()
        )
        if wfh is None:
            return error('You have no approved work-from-home request for this date.')

        report = WFHDailyReport.objects.filter(employee=request.user, date=day).first()
        if report and report.review_status != WFHDailyReport.REVIEW_PENDING:
            return error('This report has already been reviewed and can no longer be changed.')
        fields = {k: data[k] for k in ('completed_work', 'pending_work', 'updates')}
        if report:
            # Edits keep the original submission time; a late edit doesn't make an on-time report late.
            for k, v in fields.items():
                setattr(report, k, v)
            report.save(update_fields=list(fields))
            created = False
        else:
            report = WFHDailyReport.objects.create(
                wfh_request=wfh, employee=request.user, date=day, submitted_late=day < today, **fields,
            )
            created = True
        _reprocess(report)
        return success(
            'Report submitted.' if created else 'Report updated.',
            data=WFHDailyReportSerializer(report, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class WFHDailyReportReviewView(APIView):
    permission_classes = [IsAuthenticated]
    _OUTCOMES = (WFHDailyReport.REVIEW_FULL_DAY, WFHDailyReport.REVIEW_HALF_DAY, WFHDailyReport.REVIEW_NOT_ACCEPTED)

    def post(self, request, report_id):
        try:
            report = WFHDailyReport.objects.select_related('employee', 'wfh_request').get(pk=report_id)
        except (WFHDailyReport.DoesNotExist, ValueError):
            return error('Report not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_review(request.user, report):
            return error('You cannot review this report.', http_status=status.HTTP_403_FORBIDDEN)
        if report.review_status != WFHDailyReport.REVIEW_PENDING:
            return error('This report has already been reviewed.')
        outcome = request.data.get('outcome')
        if outcome not in self._OUTCOMES:
            return error('outcome must be full_day, half_day or not_accepted.')
        remarks = (request.data.get('remarks') or '').strip()
        if outcome == WFHDailyReport.REVIEW_NOT_ACCEPTED and not remarks:
            return error('Please give a reason when not accepting a report.')
        report.review_status = outcome
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.review_remarks = remarks
        report.save(update_fields=['review_status', 'reviewed_by', 'reviewed_at', 'review_remarks'])
        _reprocess(report)
        return success('Report reviewed.', data=WFHDailyReportSerializer(report, context={'request': request}).data)
