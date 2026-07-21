import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from core.responses import success, error, first_error
from apps.payroll.models import StatutoryConfig
from apps.payroll.serializers import StatutoryConfigSerializer
from apps.branch.models import State

logger = logging.getLogger(__name__)

HR_ADMIN_ROLES = frozenset(['system_admin', 'hr_admin'])


def _is_hr_admin(user):
    return user.role and user.role.name in HR_ADMIN_ROLES


class StatutoryConfigListView(APIView):
    """List all state statutory configs / create one for a state."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        configs = StatutoryConfig.objects.select_related('state').order_by('state__name')
        serializer = StatutoryConfigSerializer(configs, many=True)
        return success('Statutory configs retrieved.', serializer.data)

    def post(self, request):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can create statutory configs.', http_status=403)

        state_id = request.data.get('state')
        if StatutoryConfig.objects.filter(state_id=state_id).exists():
            return error('Statutory config for this state already exists. Use PUT to update.')

        serializer = StatutoryConfigSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        config = serializer.save()
        logger.info('StatutoryConfig created for state %s by %s', config.state.name, request.user.email)
        return success('Statutory config created.', StatutoryConfigSerializer(config).data, http_status=201)


class StatutoryConfigDetailView(APIView):
    """Retrieve / update statutory config for a state."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        config = get_object_or_404(StatutoryConfig, pk=pk)
        return success('Statutory config retrieved.', StatutoryConfigSerializer(config).data)

    def put(self, request, pk):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can update statutory configs.', http_status=403)

        config = get_object_or_404(StatutoryConfig, pk=pk)
        serializer = StatutoryConfigSerializer(config, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        serializer.save()
        logger.info('StatutoryConfig for %s updated by %s', config.state.name, request.user.email)
        return success('Statutory config updated.', serializer.data)


class StatutoryConfigByStateView(APIView):
    """GET statutory config by state ID (convenience endpoint for the frontend)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, state_pk):
        state = get_object_or_404(State, pk=state_pk)
        config = StatutoryConfig.objects.filter(state=state).first()
        if config is None:
            return error('No statutory config exists for this state yet.', http_status=404)
        return success('Statutory config retrieved.', StatutoryConfigSerializer(config).data)
