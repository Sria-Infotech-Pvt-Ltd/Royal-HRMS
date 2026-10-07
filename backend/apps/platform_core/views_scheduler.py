"""Phase 3B Task H — admin API for job types, scheduled jobs, run now, run history."""
from __future__ import annotations

from core.permissions import HasSettingsPermission
from core.responses import error, success
from rest_framework.views import APIView

from apps.platform_core import services_scheduler as scheduler
from apps.platform_core.models import JobRun, JobType, ScheduledJob
from apps.platform_core.serializers_workflow import JobRunSerializer, JobTypeSerializer, ScheduledJobSerializer
from apps.platform_core.views import _BaseDetailView, _BaseListCreateView


class JobTypeListView(_BaseListCreateView):
    model = JobType
    serializer_class = JobTypeSerializer
    search_fields = ['code', 'name']


class ScheduledJobListCreateView(_BaseListCreateView):
    model = ScheduledJob
    serializer_class = ScheduledJobSerializer
    search_fields = ['name']


class ScheduledJobDetailView(_BaseDetailView):
    model = ScheduledJob
    serializer_class = ScheduledJobSerializer


class ScheduledJobRunNowView(APIView):
    permission_classes = [HasSettingsPermission]

    def post(self, request, pk):
        try:
            run = scheduler.run_now(pk, triggered_by=JobRun.TRIGGER_ADMIN, triggered_by_user=request.user)
        except ScheduledJob.DoesNotExist:
            return error('Not found.', http_status=404)
        except scheduler.SchedulerError as exc:
            return error(exc.message, http_status=409)
        return success('Run complete.', JobRunSerializer(run).data)


class JobRunListView(APIView):
    permission_classes = [HasSettingsPermission]

    def get(self, request, pk):
        from core.pagination import paginate, paginated_data
        qs = JobRun.objects.filter(scheduled_job_id=pk)
        page_obj, paginator = paginate(qs, request)
        return success('Run history retrieved.', paginated_data(paginator, page_obj, JobRunSerializer(page_obj, many=True).data))
