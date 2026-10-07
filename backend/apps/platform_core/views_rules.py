"""Phase 3A Task H — admin API for rules, rule tables, policy types,
policies, assignments, the explainer, and affected-employees. Same
HasSettingsPermission/core.responses convention as every other
platform_core endpoint (Rule 5 — no new permission-granting migrations)."""
from __future__ import annotations

import datetime

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import HasSettingsPermission
from core.responses import error, success

from apps.platform_core import services_policies as policies
from apps.platform_core import services_rule_definitions as rule_defs
from apps.platform_core import services_rules as rules
from apps.platform_core.models import (
    Policy, PolicyAssignment, PolicyType, RuleDefinition, RuleTable, RuleTableVersion, RuleTestCase,
)
from apps.platform_core.serializers_rules import (
    PolicyAssignmentSerializer, PolicySerializer, PolicyTypeSerializer,
    RuleDefinitionSerializer, RuleTableSerializer, RuleTableVersionSerializer,
    RuleTestCaseSerializer,
)
from apps.platform_core.views import _BaseDetailView, _BaseListCreateView


# ─── Rules ───────────────────────────────────────────────────────────────────

class RuleDefinitionListCreateView(_BaseListCreateView):
    model = RuleDefinition
    serializer_class = RuleDefinitionSerializer
    search_fields = ['code', 'name']
    ordering = ['module', 'code']


class RuleDefinitionDetailView(_BaseDetailView):
    model = RuleDefinition
    serializer_class = RuleDefinitionSerializer


class RuleValidateView(APIView):
    """Type-check only, no test execution, no publish — Task C.5's
    "validate (type-check)" admin action."""
    permission_classes = [HasSettingsPermission]

    def post(self, request, pk):
        rule = RuleDefinition.objects.filter(pk=pk).first()
        if rule is None:
            return error('Not found.', http_status=404)
        errors = rule_defs.type_check(rule)
        return success('Type-check complete.', {'valid': not errors, 'errors': errors})


class RuleTestRunView(APIView):
    """Ad-hoc test-run with inputs from the request body (not a saved
    RuleTestCase) — Task C.5's "test-run with ad-hoc inputs"."""
    permission_classes = [HasSettingsPermission]

    def post(self, request, pk):
        rule = RuleDefinition.objects.filter(pk=pk).first()
        if rule is None:
            return error('Not found.', http_status=404)
        try:
            result = rules.evaluate(rule.expression, request.data.get('inputs') or {})
        except Exception as exc:
            return error(f'Evaluation failed: {exc}', http_status=400)
        return success('Evaluated.', {'result': rule_defs.jsonable(result)})


class RulePublishView(APIView):
    permission_classes = [HasSettingsPermission]

    def post(self, request, pk):
        rule = RuleDefinition.objects.filter(pk=pk).first()
        if rule is None:
            return error('Not found.', http_status=404)
        effective_from = request.data.get('effective_from')
        if effective_from:
            effective_from = datetime.date.fromisoformat(effective_from)
        try:
            version = rule_defs.publish(rule, actor=request.user, effective_from=effective_from)
        except rule_defs.RulePublishError as exc:
            return error(exc.message, data={'errors': exc.errors}, http_status=400)
        return success('Rule published.', {'version': version.version, 'effective_from': str(version.effective_from)})


class RuleRetireView(APIView):
    permission_classes = [HasSettingsPermission]

    def post(self, request, pk):
        rule = RuleDefinition.objects.filter(pk=pk).first()
        if rule is None:
            return error('Not found.', http_status=404)
        try:
            rule_defs.retire(rule)
        except rule_defs.RulePublishError as exc:
            return error(exc.message, data={'usages': exc.errors}, http_status=400)
        return success('Rule retired.')


class RuleWhereUsedView(APIView):
    permission_classes = [HasSettingsPermission]

    def get(self, request, pk):
        rule = RuleDefinition.objects.filter(pk=pk).first()
        if rule is None:
            return error('Not found.', http_status=404)
        return success('Where-used computed.', {'usages': rule_defs.where_used(rule)})


class RuleVersionListView(APIView):
    permission_classes = [HasSettingsPermission]

    def get(self, request, pk):
        rule = RuleDefinition.objects.filter(pk=pk).first()
        if rule is None:
            return error('Not found.', http_status=404)
        from apps.platform_core.serializers_rules import RuleVersionSerializer
        return success('Versions retrieved.', RuleVersionSerializer(rule.versions.all(), many=True).data)


class RuleTestCaseListCreateView(_BaseListCreateView):
    model = RuleTestCase
    serializer_class = RuleTestCaseSerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        rule_id = request.query_params.get('rule')
        if rule_id:
            qs = qs.filter(rule_id=rule_id)
        return qs


class RuleTestCaseDetailView(_BaseDetailView):
    model = RuleTestCase
    serializer_class = RuleTestCaseSerializer


class RuleTableListCreateView(_BaseListCreateView):
    model = RuleTable
    serializer_class = RuleTableSerializer
    search_fields = ['code', 'description']


class RuleTableDetailView(_BaseDetailView):
    model = RuleTable
    serializer_class = RuleTableSerializer


class RuleTableVersionListCreateView(_BaseListCreateView):
    model = RuleTableVersion
    serializer_class = RuleTableVersionSerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        table_id = request.query_params.get('table')
        if table_id:
            qs = qs.filter(table_id=table_id)
        return qs


# ─── Policies ────────────────────────────────────────────────────────────────

class PolicyTypeListView(_BaseListCreateView):
    """Read-mostly (Task H.1 "policy types (read)") — POST still exists
    for the developer-registration command's own convenience, but
    PolicyType rows are meant to be created by sync_policy_types, not
    ad-hoc admin typing."""
    model = PolicyType
    serializer_class = PolicyTypeSerializer
    search_fields = ['code', 'name']


class PolicyListCreateView(_BaseListCreateView):
    model = Policy
    serializer_class = PolicySerializer
    search_fields = ['code', 'name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        type_code = request.query_params.get('type')
        if type_code:
            qs = qs.filter(type__code=type_code)
        return qs


class PolicyDetailView(_BaseDetailView):
    model = Policy
    serializer_class = PolicySerializer


class PolicyAssignmentListCreateView(_BaseListCreateView):
    model = PolicyAssignment
    serializer_class = PolicyAssignmentSerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        policy_id = request.query_params.get('policy')
        if policy_id:
            qs = qs.filter(policy_id=policy_id)
        return qs


class PolicyAssignmentDetailView(_BaseDetailView):
    model = PolicyAssignment
    serializer_class = PolicyAssignmentSerializer


class PolicyExplainerView(APIView):
    """Task E — GET /api/v1/platform/policies/effective?employee=&type=&as_of="""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import User
        type_code = request.query_params.get('type')
        employee_id = request.query_params.get('employee')
        as_of_raw = request.query_params.get('as_of')
        if not type_code or not employee_id:
            return error('"type" and "employee" query parameters are required.', http_status=400)
        employee = User.objects.filter(pk=employee_id).first()
        if employee is None:
            return error('Unknown employee.', http_status=404)
        as_of = datetime.date.fromisoformat(as_of_raw) if as_of_raw else datetime.date.today()
        try:
            result = policies.explain(type_code, employee, as_of)
        except policies.PolicyResolutionError as exc:
            return error(exc.message, http_status=404)
        return success('Explained.', result)


class PolicyAffectedEmployeesView(APIView):
    """GET /api/v1/platform/policies/<id>/affected-employees?as_of=
    Returns a count + paginated list of employees this policy would
    currently win for — built on resolve_many against every active
    employee (permission-aware: requires settings.view, same as the rest
    of this admin surface)."""
    permission_classes = [HasSettingsPermission]

    def get(self, request, pk):
        from apps.accounts.models import User
        from core.pagination import paginate, paginated_data

        policy = Policy.objects.filter(pk=pk).first()
        if policy is None:
            return error('Not found.', http_status=404)
        as_of_raw = request.query_params.get('as_of')
        as_of = datetime.date.fromisoformat(as_of_raw) if as_of_raw else datetime.date.today()

        employees = list(User.objects.filter(is_active=True))
        results = policies.resolve_many(policy.type.code, employees, as_of)
        affected_ids = [emp_id for emp_id, params in results.items() if params == policy.parameters]
        affected = [e for e in employees if e.pk in affected_ids]

        page_obj, paginator = paginate(affected, request)
        data = [{'id': e.pk, 'email': e.email, 'full_name': getattr(e, 'full_name', '')} for e in page_obj]
        return success('Affected employees computed.', paginated_data(paginator, page_obj, data))
