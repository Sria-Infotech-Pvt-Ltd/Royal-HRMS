import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from core.responses import success, error, first_error
from core.permissions import has_perm as _has_perm
from apps.payroll.models import SalaryStructure, SalaryComponent
from apps.payroll.serializers import (
    SalaryStructureSerializer,
    SalaryStructureListSerializer,
    SalaryComponentSerializer,
)

logger = logging.getLogger(__name__)


class SalaryStructureListView(APIView):
    """List all salary structures / create a new one."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary structures.', http_status=403)

        structures = SalaryStructure.objects.filter(is_active=True).order_by('name')
        serializer = SalaryStructureListSerializer(structures, many=True)
        return success('Salary structures retrieved.', serializer.data)

    def post(self, request):
        if not _has_perm(request.user, 'payroll.create'):
            return error('Only HR admin can create salary structures.', http_status=403)

        serializer = SalaryStructureListSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        # Only one default allowed
        if request.data.get('is_default'):
            SalaryStructure.objects.filter(is_default=True).update(is_default=False)

        structure = serializer.save()
        logger.info('Salary structure "%s" created by %s', structure.name, request.user.email)
        return success('Salary structure created.', SalaryStructureSerializer(structure).data, http_status=201)


class SalaryStructureDetailView(APIView):
    """Retrieve / update / soft-delete a single salary structure."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary structures.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=pk)
        serializer = SalaryStructureSerializer(structure)
        return success('Salary structure retrieved.', serializer.data)

    def put(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update salary structures.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=pk)
        serializer = SalaryStructureListSerializer(structure, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        if request.data.get('is_default'):
            SalaryStructure.objects.exclude(pk=pk).filter(is_default=True).update(is_default=False)

        serializer.save()
        return success('Salary structure updated.', SalaryStructureSerializer(structure).data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'payroll.delete'):
            return error('Only HR admin can delete salary structures.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=pk)
        if structure.is_default:
            return error('Cannot delete the default salary structure.')
        structure.is_active = False
        structure.save(update_fields=['is_active', 'updated_at'])
        return success('Salary structure deactivated.')


class SalaryComponentListView(APIView):
    """List components in a structure / add a new component."""

    permission_classes = [IsAuthenticated]

    def get(self, request, structure_pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary components.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=structure_pk)
        components = structure.components.filter(is_active=True)
        serializer = SalaryComponentSerializer(components, many=True)
        return success('Components retrieved.', serializer.data)

    def post(self, request, structure_pk):
        if not _has_perm(request.user, 'payroll.create'):
            return error('Only HR admin can add components.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=structure_pk)
        serializer = SalaryComponentSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        component = serializer.save(structure=structure)
        logger.info(
            'Component "%s" added to structure "%s" by %s',
            component.name, structure.name, request.user.email,
        )
        return success('Component added.', SalaryComponentSerializer(component).data, http_status=201)


class SalaryComponentDetailView(APIView):
    """Update / soft-delete a single component."""

    permission_classes = [IsAuthenticated]

    def put(self, request, structure_pk, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update components.', http_status=403)

        component = get_object_or_404(SalaryComponent, pk=pk, structure__pk=structure_pk)
        serializer = SalaryComponentSerializer(component, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        serializer.save()
        return success('Component updated.', serializer.data)

    def delete(self, request, structure_pk, pk):
        if not _has_perm(request.user, 'payroll.delete'):
            return error('Only HR admin can delete components.', http_status=403)

        component = get_object_or_404(SalaryComponent, pk=pk, structure__pk=structure_pk)
        component.is_active = False
        component.save(update_fields=['is_active', 'updated_at'])
        return success('Component deactivated.')
