import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from core.responses import success, error, first_error
from apps.payroll.models import StatutoryConfig
from apps.payroll.serializers import StatutoryConfigSerializer
from apps.branch.models import State

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class StatutoryConfigListView(APIView):
    """List all state statutory configs / create one for a state."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        configs = StatutoryConfig.objects.select_related('state').order_by('state__name')
        serializer = StatutoryConfigSerializer(configs, many=True)
        return success('Statutory configs retrieved.', serializer.data)

    def post(self, request):
        if not _has_perm(request.user, 'payroll.create'):
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
        if not _has_perm(request.user, 'payroll.edit'):
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
