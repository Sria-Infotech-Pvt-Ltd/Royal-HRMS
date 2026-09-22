import logging

from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from apps.accounts.models import AuditLog, PromotionRecord, Role, User
from apps.branch.models import Branch, City, State
from apps.branch.serializers import BranchSerializer, CitySerializer, StateSerializer
from apps.branch.utils import generate_branch_code

logger = logging.getLogger(__name__)

_PERM_DENIED = 'You do not have permission to perform this action.'


def _branch_out_of_scope(user, branch) -> bool:
    """
    Non-org-wide users (no settings.edit — e.g. Branch Admin) may only edit
    their own assigned branch's record, never another one. settings.edit
    holders (system_admin) bypass this entirely, same as every other scope
    check in this codebase. Mirrors _employee_out_of_branch_scope in
    apps/accounts/views.py.
    """
    if _has_perm(user, 'settings.edit'):
        return False
    return (user.branch or '').strip().lower() != (branch.branch_name or '').strip().lower()


def _cascade_hr(branch: Branch, old_hr_id) -> None:
    """When branch HR changes, update hr field for all employees in that branch
    who were pointing at the old HR (preserves manual overrides). Module-level
    (not a BranchDetailView method) so BranchReassignAdminView can reuse it
    without duplicating the logic.
    """
    if branch.hr_id == old_hr_id:
        return
    base_qs = User.objects.filter(branch__iexact=branch.branch_name, is_active=True)
    if branch.hr_id:
        base_qs = base_qs.exclude(pk=branch.hr_id)

    if branch.hr_id:
        # Update employees whose hr still points at the old HR value
        base_qs.filter(hr_id=old_hr_id).update(hr_id=branch.hr_id)
    else:
        base_qs.filter(hr_id=old_hr_id).update(hr=None)


def _branch_admin_role():
    """
    The Branch Admin role, resolved by capability (can_manage_branch=True)
    rather than by name, and excluding any role that also carries
    settings.edit — mirrors the exact resolution logic the frontend already
    uses in applyLeaderRole() (BranchManagement.tsx), so both paths that can
    grant this role agree on which one it is.
    """
    return (
        Role.objects.filter(can_manage_branch=True, is_active=True)
        .exclude(role_permissions__permission__codename='settings.edit')
        .first()
    )


# ─── State & City (cascading dropdowns) ──────────────────────────────────────

class StateListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        states = State.objects.filter(is_active=True)
        return success('States retrieved successfully.', data=StateSerializer(states, many=True).data)


class CityListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, state_id):
        try:
            state = State.objects.get(pk=state_id, is_active=True)
        except State.DoesNotExist:
            return error('State not found.', http_status=status.HTTP_404_NOT_FOUND)
        cities = state.cities.filter(is_active=True)
        return success('Cities retrieved successfully.', data=CitySerializer(cities, many=True).data)


# ─── Branch code preview ──────────────────────────────────────────────────────

class BranchPreviewCodeView(APIView):
    """Returns what branch code would be generated for a given city (preview only)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'branches.create'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        city_id   = request.query_params.get('city_id')
        city_name = (request.query_params.get('city_name') or '').strip()

        if city_id:
            try:
                city_id = int(city_id)
            except (TypeError, ValueError):
                return error('city_id must be a valid integer.')
            try:
                city = City.objects.select_related('state').get(pk=city_id, is_active=True)
            except City.DoesNotExist:
                return error('City not found.', http_status=status.HTTP_404_NOT_FOUND)
            with transaction.atomic():
                code = generate_branch_code(city.name)
            return success(
                'Branch code preview generated.',
                data={'branch_code': code, 'city': city.name, 'state': city.state.name},
            )

        if city_name:
            # City not created yet (user is typing a new one) — the code only
            # depends on the name string, so preview it without a City row.
            with transaction.atomic():
                code = generate_branch_code(city_name)
            return success(
                'Branch code preview generated.',
                data={'branch_code': code, 'city': city_name, 'state': None},
            )

        return error('city_id or city_name query parameter is required.')


# ─── Branch CRUD ──────────────────────────────────────────────────────────────

class BranchListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'branches.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        qs = Branch.objects.select_related('state', 'city').all()
        # Same scoping already applied to editing a branch (_branch_out_of_scope)
        # and to every other module (employees, leave, attendance) — a
        # non-org-wide user (no settings.edit) only sees their own branch,
        # not every branch in the company.
        if not _has_perm(request.user, 'settings.edit') and request.user.branch:
            qs = qs.filter(branch_name__iexact=request.user.branch)
        if status_filter := request.query_params.get('status'):
            allowed_statuses = {Branch.STATUS_ACTIVE, Branch.STATUS_INACTIVE}
            if status_filter not in allowed_statuses:
                return error(f'status must be one of: {", ".join(sorted(allowed_statuses))}.')
            qs = qs.filter(status=status_filter)
        if state_id := request.query_params.get('state'):
            try:
                qs = qs.filter(state_id=int(state_id))
            except (TypeError, ValueError):
                return error('state filter must be a valid integer ID.')
        if city_id := request.query_params.get('city'):
            try:
                qs = qs.filter(city_id=int(city_id))
            except (TypeError, ValueError):
                return error('city filter must be a valid integer ID.')

        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 10))))
        except (ValueError, TypeError):
            page_num, page_size = 1, 10

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page_num)

        # Compute real employee counts from User table (branch is stored as a name string)
        branch_counts = dict(
            User.objects.filter(is_active=True)
            .values('branch')
            .annotate(count=Count('id'))
            .values_list('branch', 'count')
        )

        return success('Branches retrieved successfully.', data={
            'count':       paginator.count,
            'page':        page_obj.number,
            'page_size':   page_size,
            'total_pages': paginator.num_pages,
            'results':     BranchSerializer(
                page_obj.object_list, many=True,
                context={'branch_counts': branch_counts},
            ).data,
        })

    def post(self, request):
        if not _has_perm(request.user, 'branches.create'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        serializer = BranchSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            branch = serializer.save()
        except IntegrityError:
            return error(
                'A branch with this code already exists.',
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='branch_created', module='branch',
            object_id=str(branch.pk),
            changes={'branch_code': branch.branch_code, 'branch_name': branch.branch_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Branch "%s" created by %s', branch.branch_code, request.user.email)
        return success(
            'Branch created successfully.',
            data=BranchSerializer(branch).data,
            http_status=status.HTTP_201_CREATED,
        )


class BranchDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_branch(self, pk):
        try:
            return Branch.objects.select_related('state', 'city').get(pk=pk)
        except Branch.DoesNotExist:
            return None

    def get(self, request, pk):
        if not _has_perm(request.user, 'branches.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        branch = self._get_branch(pk)
        if not branch:
            return error('Branch not found.', http_status=status.HTTP_404_NOT_FOUND)
        if _branch_out_of_scope(request.user, branch):
            return error('Branch not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Branch retrieved successfully.', data=BranchSerializer(branch).data)

    def put(self, request, pk):
        if not _has_perm(request.user, 'branches.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        branch = self._get_branch(pk)
        if not branch:
            return error('Branch not found.', http_status=status.HTTP_404_NOT_FOUND)
        if _branch_out_of_scope(request.user, branch):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        old_hr_id = branch.hr_id
        serializer = BranchSerializer(branch, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                'A branch with this name or code already exists.',
                http_status=status.HTTP_409_CONFLICT,
            )
        _cascade_hr(updated, old_hr_id)
        AuditLog.objects.create(
            user=request.user, action='branch_updated', module='branch',
            object_id=str(updated.pk),
            changes={'branch_code': updated.branch_code, 'branch_name': updated.branch_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Branch "%s" updated by %s', updated.branch_code, request.user.email)
        return success('Branch updated successfully.', data=BranchSerializer(updated).data)

    def patch(self, request, pk):
        if not _has_perm(request.user, 'branches.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        branch = self._get_branch(pk)
        if not branch:
            return error('Branch not found.', http_status=status.HTTP_404_NOT_FOUND)
        if _branch_out_of_scope(request.user, branch):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        old_hr_id = branch.hr_id
        serializer = BranchSerializer(branch, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                'A branch with this name or code already exists.',
                http_status=status.HTTP_409_CONFLICT,
            )
        _cascade_hr(updated, old_hr_id)
        AuditLog.objects.create(
            user=request.user, action='branch_updated', module='branch',
            object_id=str(updated.pk),
            changes={'branch_code': updated.branch_code, 'branch_name': updated.branch_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Branch "%s" patched by %s', updated.branch_code, request.user.email)
        return success('Branch updated successfully.', data=BranchSerializer(updated).data)

    def post(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'branches.delete'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        branch = self._get_branch(pk)
        if not branch:
            return error('Branch not found.', http_status=status.HTTP_404_NOT_FOUND)
        code = branch.branch_code

        # User.branch is a free-text field, not a FK to Branch, so deleting a
        # Branch row never raises ProtectedError on its account — this explicit
        # count is the only thing that actually blocks deletion while employees
        # are still assigned to it.
        employee_count = User.objects.filter(branch__iexact=branch.branch_name).count()
        if employee_count:
            return error(
                f'Cannot delete branch "{code}" — {employee_count} employee'
                f'{"s" if employee_count != 1 else ""} still assigned to it. '
                'Reassign or remove them before deleting this branch.',
                http_status=status.HTTP_409_CONFLICT,
            )

        try:
            branch.delete()
        except ProtectedError:
            return error(
                f'Cannot delete branch "{code}" — it is referenced by employee records. '
                'Reassign or remove them first.',
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='branch_deleted', module='branch',
            object_id=str(branch.pk),
            changes={'branch_code': code, 'branch_name': branch.branch_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Branch "%s" deleted by %s', code, request.user.email)
        return success(f'Branch "{code}" deleted successfully.')


class BranchReassignAdminView(APIView):
    """
    POST /api/branch/branches/<pk>/reassign-admin/  — { "employee_id": "<uuid>" }

    Safely replaces a branch's Branch Admin with another eligible employee,
    in one atomic step:
      - demotes the previous admin (if any) back to the base Employee role
        (their historical attendance/leave/payroll records are untouched —
        this only ever changes their `role`/`branch` fields)
      - promotes the target employee to Branch Admin and assigns them to
        this branch
      - repoints Branch.hr at the new admin, cascading via the same
        _cascade_hr() helper BranchDetailView.put/patch already use
      - audit-logs both sides of the change

    Reuses the exact same role-resolution logic as the Add-Branch "assign an
    existing employee" flow (applyLeaderRole in BranchManagement.tsx) rather
    than introducing a second way to decide what "the Branch Admin role" is.
    Gated on branches.edit — the same permission that already guards every
    other branch-admin-affecting action (BranchDetailView.put/patch), so this
    doesn't loosen who can change a branch's admin.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'branches.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            branch = Branch.objects.select_related('hr').get(pk=pk)
        except Branch.DoesNotExist:
            return error('Branch not found.', http_status=status.HTTP_404_NOT_FOUND)
        if _branch_out_of_scope(request.user, branch):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        employee_id = (request.data.get('employee_id') or '').strip() if isinstance(request.data.get('employee_id'), str) else request.data.get('employee_id')
        if not employee_id:
            return error('employee_id is required.')
        try:
            # Looked up by the employee_id code (e.g. "EMP001"), not the row's
            # real pk — matches _get_employee()'s convention in accounts/views.py,
            # which is what the frontend's employee picker actually sends as
            # ApiEmployeeOption.id (see accounts/views.py _employee_dict: 'id' is
            # user.employee_id, 'uuid' is the real pk — two different fields).
            new_admin = User.objects.select_related('role').get(employee_id=employee_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if not new_admin.is_active:
            return error(f'{new_admin.full_name} is inactive and cannot be assigned as Branch Admin.')
        if new_admin.must_change_password:
            return error(
                f'{new_admin.full_name} has not completed onboarding yet and cannot be '
                'assigned as Branch Admin.'
            )
        if new_admin.role and new_admin.role.role_permissions.filter(permission__codename='settings.edit').exists():
            return error(
                f'{new_admin.full_name} is a Company Admin — reassign them from the '
                'Employees page instead of through Branch Admin reassignment.'
            )

        old_admin = branch.hr
        if old_admin and old_admin.pk == new_admin.pk:
            return error(f'{new_admin.full_name} is already the Branch Admin for this branch.')

        branch_admin_role = _branch_admin_role()
        if not branch_admin_role:
            return error(
                'No Branch Admin role is configured for this company.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        employee_role = Role.objects.filter(name='employee', is_active=True).first()
        if old_admin and not employee_role:
            return error(
                'The base Employee role is not configured for this company — '
                'cannot safely reassign.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        ip_address     = get_client_ip(request)
        effective_date = timezone.now().date()
        remarks        = f'Branch Admin reassignment for {branch.branch_name}.'
        with transaction.atomic():
            if old_admin and old_admin.pk != new_admin.pk:
                old_role_name = old_admin.role.name if old_admin.role else None
                old_admin.role = employee_role
                old_admin.save(update_fields=['role', 'updated_at'])
                AuditLog.objects.create(
                    user=request.user, action='branch_admin_removed', module='employees',
                    object_id=str(old_admin.id),
                    changes={
                        'employee_id': old_admin.employee_id, 'full_name': old_admin.full_name,
                        'branch': branch.branch_name,
                        'role': {'from': old_role_name, 'to': employee_role.name},
                    },
                    branch=old_admin.branch, ip_address=ip_address,
                )
                # Same history mechanism EmployeeDetailView.put() uses for any
                # role change — keeps this reassignment visible on the old
                # admin's own Promotion History tab, not just in AuditLog.
                PromotionRecord.objects.create(
                    employee=old_admin, previous_role=old_role_name or '',
                    new_role=employee_role.name,
                    previous_designation=old_admin.designation or '',
                    new_designation=old_admin.designation or '',
                    effective_date=effective_date, remarks=remarks, promoted_by=request.user,
                )

            new_role_name = new_admin.role.name if new_admin.role else None
            old_new_admin_branch = new_admin.branch
            new_admin.role = branch_admin_role
            new_admin.branch = branch.branch_name
            new_admin.save(update_fields=['role', 'branch', 'updated_at'])
            AuditLog.objects.create(
                user=request.user, action='branch_admin_assigned', module='employees',
                object_id=str(new_admin.id),
                changes={
                    'employee_id': new_admin.employee_id, 'full_name': new_admin.full_name,
                    'branch': {'from': old_new_admin_branch, 'to': branch.branch_name},
                    'role': {'from': new_role_name, 'to': branch_admin_role.name},
                },
                branch=branch.branch_name, ip_address=ip_address,
            )
            PromotionRecord.objects.create(
                employee=new_admin, previous_role=new_role_name or '',
                new_role=branch_admin_role.name,
                previous_designation=new_admin.designation or '',
                new_designation=new_admin.designation or '',
                effective_date=effective_date, remarks=remarks, promoted_by=request.user,
            )

            old_hr_id = branch.hr_id
            branch.hr = new_admin
            branch.save(update_fields=['hr', 'updated_at'])
            _cascade_hr(branch, old_hr_id)

            AuditLog.objects.create(
                user=request.user, action='branch_admin_reassigned', module='branch',
                object_id=str(branch.pk),
                changes={
                    'branch_code': branch.branch_code, 'branch_name': branch.branch_name,
                    'previous_admin': {'id': str(old_admin.id), 'name': old_admin.full_name} if old_admin else None,
                    'new_admin': {'id': str(new_admin.id), 'name': new_admin.full_name},
                },
                branch=branch.branch_name, ip_address=ip_address,
            )

        logger.info(
            'Branch "%s" admin reassigned from %s to %s by %s',
            branch.branch_code, old_admin.email if old_admin else '(none)',
            new_admin.email, request.user.email,
        )
        branch.refresh_from_db()
        return success(
            f'Branch Admin for "{branch.branch_name}" reassigned to {new_admin.full_name}.',
            data=BranchSerializer(branch).data,
        )


# ─── Branch Geofencing ───────────────────────────────────────────────────────

class BranchGeofencingView(APIView):
    """
    GET  /api/branch/branches/<pk>/geofencing/  — read current geofence config
    PUT  /api/branch/branches/<pk>/geofencing/  — set latitude, longitude, radius, enabled flag
    """

    permission_classes = [IsAuthenticated]

    def _get_branch(self, pk):
        try:
            return Branch.objects.get(pk=pk)
        except Branch.DoesNotExist:
            return None

    def get(self, request, pk):
        if not _has_perm(request.user, 'branches.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        branch = self._get_branch(pk)
        if not branch:
            return error('Branch not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Geofencing config retrieved successfully.', data={
            'id':                   branch.pk,
            'branch_name':          branch.branch_name,
            'branch_code':          branch.branch_code,
            'latitude':             str(branch.latitude) if branch.latitude is not None else None,
            'longitude':            str(branch.longitude) if branch.longitude is not None else None,
            'allowed_radius_meters': branch.allowed_radius_meters,
            'geofencing_enabled':   branch.geofencing_enabled,
            'has_coordinates':      branch.has_coordinates,
        })

    def put(self, request, pk):
        if not _has_perm(request.user, 'branches.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        branch = self._get_branch(pk)
        if not branch:
            return error('Branch not found.', http_status=status.HTTP_404_NOT_FOUND)
        if _branch_out_of_scope(request.user, branch):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        from rest_framework import serializers as drf_serializers

        class GeofencingSerializer(drf_serializers.Serializer):
            latitude              = drf_serializers.FloatField(required=False, allow_null=True)
            longitude             = drf_serializers.FloatField(required=False, allow_null=True)
            allowed_radius_meters = drf_serializers.IntegerField(min_value=10, max_value=5000, required=False)
            geofencing_enabled    = drf_serializers.BooleanField(required=False)

            def validate(self, attrs):
                lat = attrs.get('latitude')
                lon = attrs.get('longitude')
                if (lat is None) != (lon is None):
                    raise drf_serializers.ValidationError(
                        'Both latitude and longitude must be provided together.'
                    )
                return attrs

        serializer = GeofencingSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors,
                         http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        data = serializer.validated_data
        if 'latitude'              in data: branch.latitude              = data['latitude']
        if 'longitude'             in data: branch.longitude             = data['longitude']
        if 'allowed_radius_meters' in data: branch.allowed_radius_meters = data['allowed_radius_meters']
        if 'geofencing_enabled'    in data: branch.geofencing_enabled    = data['geofencing_enabled']

        # Validate after applying: can't enable without coordinates (sent now or already on branch)
        if branch.geofencing_enabled and not branch.has_coordinates:
            return error(
                'Set latitude and longitude before enabling geofencing.',
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        branch.save(update_fields=['latitude', 'longitude', 'allowed_radius_meters', 'geofencing_enabled', 'updated_at'])

        AuditLog.objects.create(
            user=request.user, action='branch_geofencing_updated', module='branch',
            object_id=str(branch.pk),
            changes={
                'latitude':             str(branch.latitude),
                'longitude':            str(branch.longitude),
                'allowed_radius_meters': branch.allowed_radius_meters,
                'geofencing_enabled':   branch.geofencing_enabled,
            },
            ip_address=get_client_ip(request),
        )
        logger.info('Branch "%s" geofencing updated by %s', branch.branch_code, request.user.email)

        return success('Geofencing configuration updated successfully.', data={
            'id':                    branch.pk,
            'branch_name':           branch.branch_name,
            'branch_code':           branch.branch_code,
            'latitude':              str(branch.latitude) if branch.latitude is not None else None,
            'longitude':             str(branch.longitude) if branch.longitude is not None else None,
            'allowed_radius_meters': branch.allowed_radius_meters,
            'geofencing_enabled':    branch.geofencing_enabled,
            'has_coordinates':       branch.has_coordinates,
        })


# ─── Stats ────────────────────────────────────────────────────────────────────

class BranchStatsView(APIView):
    """
    Returns dashboard counts:
      total_employees, total_branches, total_active_branches,
      total_inactive_branches, total_cities
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'branches.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        total_branches = Branch.objects.count()
        total_active = Branch.objects.filter(status=Branch.STATUS_ACTIVE).count()
        total_employees = User.objects.filter(is_active=True).count()
        total_cities = Branch.objects.values('city').distinct().count()
        return success('Branch statistics retrieved successfully.', data={
            'total_employees': total_employees,
            'total_branches': total_branches,
            'total_active_branches': total_active,
            'total_inactive_branches': total_branches - total_active,
            'total_cities': total_cities,
        })


# ─── Distribution (bar graph) ─────────────────────────────────────────────────

class BranchDistributionView(APIView):
    """
    Returns employee count per branch for the bar chart.
    Response: [{"branch": "Bengaluru HQ", "employees": 4}, ...]
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'branches.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        branch_counts = dict(
            User.objects.filter(is_active=True)
            .values('branch')
            .annotate(count=Count('id'))
            .values_list('branch', 'count')
        )

        branches = (
            Branch.objects
            .filter(status=Branch.STATUS_ACTIVE)
            .values('branch_name', 'branch_code')
        )
        data = sorted(
            [
                {
                    'branch': b['branch_name'],
                    'branch_code': b['branch_code'],
                    'employees': branch_counts.get(b['branch_name'], 0),
                }
                for b in branches
            ],
            key=lambda x: x['employees'],
            reverse=True,
        )
        return success('Employee distribution by branch retrieved successfully.', data=data)
