import json
import logging
import re
import uuid
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date
from django.utils.text import slugify

from core.responses import success, error, first_error, get_client_ip
from core.permissions import has_perm as _has_perm
from apps.accounts.models import AuditLog
from apps.payroll.models import SalaryStructure, SalaryComponent, SalaryComponentRevision, PayComponent
from apps.payroll.serializers import (
    SalaryStructureSerializer,
    SalaryStructureListSerializer,
    SalaryComponentSerializer,
    CompanyAllowanceSerializer,
)
from apps.payroll.services_salary_structure import (
    affected_employee_count,
    component_fields,
    component_configuration,
    create_component_code,
    next_pay_cycle_start,
    structure_component_configurations,
)

logger = logging.getLogger(__name__)


def _component_effective_date(request):
    raw_date = request.data.get('effective_from')
    effective_from = parse_date(str(raw_date)) if raw_date else next_pay_cycle_start()
    if effective_from is None:
        return None, error('Effective date must use YYYY-MM-DD format.')
    if effective_from < next_pay_cycle_start():
        return None, error(
            f'Changes must take effect on or after {next_pay_cycle_start().isoformat()}.',
        )
    return effective_from, None


def _component_response(component):
    config = component_configuration(component, include_future=True)
    if config is None:
        return None
    config['affected_employee_count'] = affected_employee_count(component.structure)
    return config


def _audit_change(request, action, object_id, changes):
    # Configurations carry dates, decimals and ids; the audit log stores plain JSON.
    changes = json.loads(json.dumps(changes, cls=DjangoJSONEncoder))
    AuditLog.objects.create(
        user=request.user,
        action=action,
        module='payroll',
        object_id=str(object_id),
        branch=request.user.branch,
        ip_address=get_client_ip(request),
        changes=changes,
    )


def _audit_component_change(request, component, action, old_config, new_config, effective_from):
    _audit_change(request, action, component.pk, {
        'structure_id': str(component.structure_id),
        'structure_name': component.structure.name,
        'component_code': component.code,
        'effective_from': effective_from.isoformat(),
        'before': old_config,
        'after': new_config,
    })


def _structure_snapshot(structure):
    return {
        'name': structure.name,
        'description': structure.description,
        'is_default': structure.is_default,
        'is_active': structure.is_active,
    }


def _allowance_snapshot(allowance):
    return {
        'code': allowance.code,
        'name': allowance.name,
        'payslip_label': allowance.payslip_label,
        'is_taxable': allowance.is_taxable,
        'is_active': allowance.is_active,
        'display_order': allowance.display_order,
    }


class CompanyAllowanceListCreateView(APIView):
    """Manage the company-wide catalogue of allowances available to structures."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view payroll allowances.', http_status=403)
        allowances = PayComponent.objects.filter(is_company_allowance=True).order_by('display_order', 'name')
        return success('Payroll allowance catalogue retrieved.', CompanyAllowanceSerializer(allowances, many=True).data)

    def post(self, request):
        if not _has_perm(request.user, 'payroll.create'):
            return error('Only HR admin can add payroll allowances.', http_status=403)

        serializer = CompanyAllowanceSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        name = serializer.validated_data['name']
        stem = re.sub(r'[^A-Z0-9]+', '_', slugify(name).replace('-', '_').upper()).strip('_') or 'ALLOWANCE'
        stem = f'ALW_{stem}'[:40].rstrip('_')
        code = stem
        suffix = 2
        while PayComponent.objects.filter(code=code).exists():
            suffix_text = f'_{suffix}'
            code = f'{stem[:40 - len(suffix_text)]}{suffix_text}'
            suffix += 1

        try:
            with transaction.atomic():
                allowance = serializer.save(
                    code=code,
                    category=PayComponent.CATEGORY_EARNING,
                    calculation_method=PayComponent.METHOD_INPUT,
                    status=PayComponent.STATUS_PUBLISHED,
                    is_active=True,
                    is_company_allowance=True,
                    payslip_group='Earnings',
                )
                _audit_change(request, 'payroll_allowance_created', allowance.pk, {'before': {}, 'after': _allowance_snapshot(allowance)})
        except IntegrityError:
            return error(
                'An allowance with this name or code was added concurrently. Refresh the catalogue and try again.',
                http_status=409,
            )
        logger.info('Payroll allowance "%s" added by %s', allowance.name, request.user.email)
        return success('Payroll allowance added.', CompanyAllowanceSerializer(allowance).data, http_status=201)


class CompanyAllowanceDetailView(APIView):
    """Update or deactivate a catalogue entry without changing existing structures."""

    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update payroll allowances.', http_status=403)

        allowance = get_object_or_404(PayComponent, pk=pk, is_company_allowance=True)
        serializer = CompanyAllowanceSerializer(allowance, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        before = _allowance_snapshot(allowance)
        with transaction.atomic():
            serializer.save()
            after = _allowance_snapshot(allowance)
            if after != before:
                _audit_change(request, 'payroll_allowance_updated', allowance.pk, {'before': before, 'after': after})
        return success('Payroll allowance updated.', serializer.data)


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
        with transaction.atomic():
            if request.data.get('is_default'):
                SalaryStructure.objects.filter(is_default=True).update(is_default=False)
            structure = serializer.save()
            _audit_change(request, 'salary_structure_created', structure.pk, {'before': {}, 'after': _structure_snapshot(structure)})
        logger.info('Salary structure "%s" created by %s', structure.name, request.user.email)
        return success('Salary structure created.', SalaryStructureSerializer(structure).data, http_status=201)


class SalaryStructureDetailView(APIView):
    """Retrieve / update / soft-delete a single salary structure."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary structures.', http_status=403)
        structure = get_object_or_404(SalaryStructure, pk=pk)
        effective_as_of = None
        if request.query_params.get('as_of'):
            effective_as_of = parse_date(request.query_params['as_of'])
            if effective_as_of is None:
                return error('as_of must use YYYY-MM-DD format.')
        serializer = SalaryStructureSerializer(
            structure,
            context={'effective_as_of': effective_as_of, 'include_future': effective_as_of is None},
        )
        return success('Salary structure retrieved.', serializer.data)

    def put(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update salary structures.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=pk)
        serializer = SalaryStructureListSerializer(structure, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        before = _structure_snapshot(structure)
        with transaction.atomic():
            if request.data.get('is_default'):
                SalaryStructure.objects.exclude(pk=pk).filter(is_default=True).update(is_default=False)
            serializer.save()
            after = _structure_snapshot(structure)
            if after != before:
                _audit_change(request, 'salary_structure_updated', structure.pk, {'before': before, 'after': after})
        return success('Salary structure updated.', SalaryStructureSerializer(structure).data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'payroll.delete'):
            return error('Only HR admin can delete salary structures.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=pk)
        if structure.is_default:
            return error('Cannot delete the default salary structure.')
        in_use = affected_employee_count(structure)
        if in_use:
            return error(
                f'{in_use} employee(s) use this structure. Move them to another structure before deleting it.',
                http_status=409,
            )
        before = _structure_snapshot(structure)
        with transaction.atomic():
            structure.is_active = False
            structure.save(update_fields=['is_active', 'updated_at'])
            _audit_change(request, 'salary_structure_deleted', structure.pk, {'before': before, 'after': _structure_snapshot(structure)})
        return success('Salary structure deactivated.')


class SalaryComponentListView(APIView):
    """List components in a structure / add a new component."""

    permission_classes = [IsAuthenticated]

    def get(self, request, structure_pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary components.', http_status=403)
        structure = get_object_or_404(SalaryStructure, pk=structure_pk)
        components = structure_component_configurations(structure, include_future=True)
        for component in components:
            component['affected_employee_count'] = affected_employee_count(structure)
        return success('Components retrieved.', components)

    def post(self, request, structure_pk):
        if not _has_perm(request.user, 'payroll.create'):
            return error('Only HR admin can add components.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=structure_pk)
        effective_from, date_error = _component_effective_date(request)
        if date_error:
            return date_error
        serializer = SalaryComponentSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        configuration = serializer.validated_data
        with transaction.atomic():
            component = serializer.save(
                structure=structure,
                code=create_component_code(structure, configuration['name']),
            )
            # Store the saved component's own values: fields the client left out (is_active, order, ...) take
            # the model defaults, and every revision must carry the full set.
            revision = SalaryComponentRevision.objects.create(
                component=component,
                effective_from=effective_from,
                configuration=component_fields(component),
                created_by=request.user,
            )
            _audit_component_change(
                request,
                component,
                'salary_component_created',
                {},
                revision.configuration,
                effective_from,
            )
        logger.info('Component "%s" scheduled for structure "%s" by %s', component.name, structure.name, request.user.email)
        response = _component_response(component)
        response['effective_from'] = effective_from.isoformat()
        return success('Component scheduled.', response, http_status=201)


class SalaryComponentDetailView(APIView):
    """Update / soft-delete a single component."""

    permission_classes = [IsAuthenticated]

    def put(self, request, structure_pk, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update components.', http_status=403)

        component = get_object_or_404(SalaryComponent, pk=pk, structure__pk=structure_pk)
        effective_from, date_error = _component_effective_date(request)
        if date_error:
            return date_error
        old_config = component_configuration(component, include_future=True)
        if old_config is None:
            old_config = {}
        changes = {
            key: value
            for key, value in request.data.items()
            if key != 'effective_from'
        }
        updated_config = {
            key: old_config[key]
            for key in (
                'name', 'component_type', 'calculation_type', 'value',
                'is_taxable', 'is_active', 'order',
            )
            if key in old_config
        }
        updated_config.update(changes)
        serializer = SalaryComponentSerializer(data=updated_config)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        new_config = {
            **serializer.validated_data,
            'code': component.code,
            'value': str(serializer.validated_data['value']),
        }
        reset_override = (
            new_config['is_active']
            and (
                not old_config.get('is_active', False)
                or old_config.get('reset_override', False)
            )
        )
        with transaction.atomic():
            revision, _ = SalaryComponentRevision.objects.update_or_create(
                component=component,
                effective_from=effective_from,
                defaults={
                    'configuration': new_config,
                    'reset_override': reset_override,
                    'created_by': request.user,
                },
            )
            _audit_component_change(
                request,
                component,
                'salary_component_updated',
                old_config,
                {**new_config, 'reset_override': reset_override},
                effective_from,
            )
        response = _component_response(component)
        response['effective_from'] = effective_from.isoformat()
        return success('Component change scheduled.', response)

    def delete(self, request, structure_pk, pk):
        if not _has_perm(request.user, 'payroll.delete'):
            return error('Only HR admin can delete components.', http_status=403)

        component = get_object_or_404(SalaryComponent, pk=pk, structure__pk=structure_pk)
        effective_from, date_error = _component_effective_date(request)
        if date_error:
            return date_error
        old_config = component_configuration(component, include_future=True)
        if old_config is None:
            return error('Component configuration is unavailable.')
        new_config = {**old_config, 'is_active': False}
        new_config = {
            key: new_config[key]
            for key in (
                'code', 'name', 'component_type', 'calculation_type', 'value',
                'is_taxable', 'is_active', 'order',
            )
        }
        with transaction.atomic():
            SalaryComponentRevision.objects.update_or_create(
                component=component,
                effective_from=effective_from,
                defaults={
                    'configuration': new_config,
                    'reset_override': False,
                    'created_by': request.user,
                },
            )
            _audit_component_change(
                request,
                component,
                'salary_component_deactivated',
                old_config,
                new_config,
                effective_from,
            )
        return success(
            'Component deactivation scheduled.',
            {'effective_from': effective_from.isoformat(), 'affected_employee_count': affected_employee_count(component.structure)},
        )


class SalaryComponentReorderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, structure_pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can reorder salary components.', http_status=403)
        structure = get_object_or_404(SalaryStructure, pk=structure_pk)
        component_ids = request.data.get('component_ids')
        if (
            not isinstance(component_ids, list)
            or not component_ids
            or not all(isinstance(component_id, str) for component_id in component_ids)
        ):
            return error('component_ids must be a non-empty list of unique component IDs.')
        try:
            component_ids = [str(uuid.UUID(component_id)) for component_id in component_ids]
        except ValueError:
            return error('Every component ID must be a valid UUID.')
        if len(component_ids) != len(set(component_ids)):
            return error('component_ids must contain unique component IDs.')
        components = list(structure.components.filter(pk__in=component_ids))
        if len(components) != len(component_ids):
            return error('Every component ID must belong to this salary structure.')
        effective_from, date_error = _component_effective_date(request)
        if date_error:
            return date_error

        by_id = {str(component.pk): component for component in components}
        with transaction.atomic():
            for index, component_id in enumerate(component_ids):
                component = by_id[component_id]
                old_config = component_configuration(component, include_future=True) or {}
                new_config = {
                    key: old_config[key]
                    for key in (
                        'code', 'name', 'component_type', 'calculation_type',
                        'value', 'is_taxable', 'is_active',
                    )
                }
                new_config['order'] = index * 10
                reset_override = old_config.get('reset_override', False) and new_config['is_active']
                SalaryComponentRevision.objects.update_or_create(
                    component=component,
                    effective_from=effective_from,
                    defaults={
                        'configuration': new_config,
                        'reset_override': reset_override,
                        'created_by': request.user,
                    },
                )
                _audit_component_change(
                    request,
                    component,
                    'salary_component_reordered',
                    old_config,
                    {**new_config, 'reset_override': reset_override},
                    effective_from,
                )
        return success(
            'Component order scheduled.',
            {'effective_from': effective_from.isoformat(), 'affected_employee_count': affected_employee_count(structure)},
        )
