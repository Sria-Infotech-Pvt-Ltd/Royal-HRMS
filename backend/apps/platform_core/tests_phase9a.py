"""Phase 9A — report builder security, document engine, config transport."""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.platform_core.models import (
    ConfigObjectType, ConfigPackage, CustomRecord, DocumentTemplate, EntityDefinition,
    FieldDefinition, FieldPermission, ReportDefinition,
)
from apps.platform_core.services_config_transport import (
    PersonalDataInRegistryError, SignatureInvalidError, TransportConflictError,
    apply_package, assert_no_personal_data, dry_run_diff, export_package, rollback_package, seed_registry,
)
from apps.platform_core.services_document_engine import (
    SensitiveFieldNotPermittedError, UndeclaredVariableError, generate_document, issue_document,
    record_click_to_accept, render_template, revoke_and_reissue,
)
from apps.platform_core.models import RoleAssignment
from apps.platform_core.services_report_builder import ReportSecurityError, run_report


def _grant_scope_all(user, role):
    import datetime as _dt
    return RoleAssignment.objects.create(
        user=user, role=role, scope_type=RoleAssignment.SCOPE_ALL, effective_from=_dt.date(2020, 1, 1),
    )
from apps.payroll.models import PayComponent
from apps.performance.models import RatingScale

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee(role=None):
    role = role or make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


def _make_entity():
    return EntityDefinition.objects.create(code=_unique('entity'), label='Test Entity', kind=EntityDefinition.KIND_CUSTOM)


class ReportBuilderSecurityTests(TestCase):
    def test_hidden_field_blocks_report_validation(self):
        entity = _make_entity()
        sensitive_field = FieldDefinition.objects.create(entity=entity, code='amount', label='Amount', data_type='decimal', is_sensitive=True)
        role = make_role(_unique('role'))
        from apps.platform_core.services_report_builder import validate_definition
        report = ReportDefinition.objects.create(
            code=_unique('RPT'), name='x', base_entity=entity, columns=[{'field_code': 'amount'}],
        )
        FieldPermission.objects.create(role=role, entity=entity, field_code='amount', access='hidden')
        with self.assertRaises(ReportSecurityError):
            validate_definition(report, role)

    def test_masked_field_is_masked_in_results(self):
        entity = _make_entity()
        FieldDefinition.objects.create(entity=entity, code='salary', label='Salary', data_type='decimal', is_sensitive=True)
        role = make_role(_unique('role'))
        employee = _make_employee(role)
        _grant_scope_all(employee, role)
        FieldPermission.objects.create(role=role, entity=entity, field_code='salary', access='masked')
        CustomRecord.objects.create(entity=entity, owner=employee, data={'salary': 100000})

        report = ReportDefinition.objects.create(
            code=_unique('RPT'), name='x', base_entity=entity, columns=[{'field_code': 'salary'}],
        )
        result = run_report(report, employee)
        self.assertEqual(len(result['rows']), 1)
        self.assertNotEqual(result['rows'][0]['salary'], 100000)

    def test_small_group_sensitive_aggregate_is_suppressed(self):
        entity = _make_entity()
        FieldDefinition.objects.create(entity=entity, code='salary', label='Salary', data_type='decimal', is_sensitive=True)
        role = make_role(_unique('role'))
        employee = _make_employee(role)
        _grant_scope_all(employee, role)
        FieldPermission.objects.create(role=role, entity=entity, field_code='salary', access='read')
        CustomRecord.objects.create(entity=entity, owner=employee, data={'salary': 100000})

        report = ReportDefinition.objects.create(
            code=_unique('RPT'), name='x', base_entity=entity, columns=[{'field_code': 'salary'}],
            aggregates=[{'field_code': 'salary', 'function': 'avg'}], min_group_size_for_sensitive_aggregate=5,
        )
        result = run_report(report, employee)
        self.assertIsNone(result['aggregates']['avg_salary'])

    def test_aggregate_shown_once_group_size_met(self):
        entity = _make_entity()
        FieldDefinition.objects.create(entity=entity, code='salary', label='Salary', data_type='decimal', is_sensitive=True)
        role = make_role(_unique('role'))
        employee = _make_employee(role)
        _grant_scope_all(employee, role)
        FieldPermission.objects.create(role=role, entity=entity, field_code='salary', access='read')
        for i in range(5):
            CustomRecord.objects.create(entity=entity, owner=employee, data={'salary': 100000 + i})

        report = ReportDefinition.objects.create(
            code=_unique('RPT'), name='x', base_entity=entity, columns=[{'field_code': 'salary'}],
            aggregates=[{'field_code': 'salary', 'function': 'count'}], min_group_size_for_sensitive_aggregate=5,
        )
        result = run_report(report, employee)
        self.assertEqual(result['aggregates']['count_salary'], 5)

    def test_calculated_column_rejects_code_execution(self):
        from apps.platform_core.services_report_builder import ReportExpressionError, _eval_calculated_column
        with self.assertRaises(ReportExpressionError):
            _eval_calculated_column('__import__("os").system("x")', {})


class DocumentEngineTests(TestCase):
    def test_undeclared_variable_blocks_generation(self):
        template = DocumentTemplate.objects.create(
            code=_unique('TPL'), name='x', document_type='x', declared_variables=['name'],
            body='Hello {{name}}, your code is {{secret_code}}.',
        )
        with self.assertRaises(UndeclaredVariableError):
            render_template(template, {'name': 'A', 'secret_code': '123'})

    def test_sensitive_variable_blocks_without_permission(self):
        template = DocumentTemplate.objects.create(
            code=_unique('TPL'), name='x', document_type='x', declared_variables=['salary'],
            body='Your salary is {{salary}}.', requires_sensitive_field_check=True,
        )
        with self.assertRaises(SensitiveFieldNotPermittedError):
            render_template(template, {'salary': '100000'}, sensitive_vars_permitted=set())
        rendered = render_template(template, {'salary': '100000'}, sensitive_vars_permitted={'salary'})
        self.assertIn('100000', rendered)

    def test_issued_document_cannot_be_reissued_only_revoked(self):
        template = DocumentTemplate.objects.create(
            code=_unique('TPL'), name='x', document_type='x', declared_variables=['name'], body='Hi {{name}}.',
        )
        employee = _make_employee()
        document = generate_document(template, {'name': 'A'}, employee)
        issue_document(document)
        document.refresh_from_db()
        self.assertEqual(document.status, document.STATUS_ISSUED)

        from apps.platform_core.services_document_engine import DocumentImmutableError
        with self.assertRaises(DocumentImmutableError):
            issue_document(document)

        new_document = revoke_and_reissue(document, {'name': 'B'}, 'Name correction.', employee)
        document.refresh_from_db()
        self.assertEqual(document.status, document.STATUS_REVOKED)
        self.assertEqual(new_document.revokes_id, document.id)

    def test_click_to_accept_moves_status_to_signed(self):
        template = DocumentTemplate.objects.create(
            code=_unique('TPL'), name='x', document_type='x', declared_variables=['name'], body='Hi {{name}}.',
        )
        employee = _make_employee()
        document = generate_document(template, {'name': 'A'}, employee)
        issue_document(document)
        record_click_to_accept(document, employee, 'employee', 'A Real Name', ip_address='127.0.0.1')
        document.refresh_from_db()
        self.assertEqual(document.status, document.STATUS_SIGNED)


class EmploymentLetterParityTests(TestCase):
    def test_rendered_letter_matches_real_generator_content(self):
        from apps.accounts.services_document_templates_seed import (
            build_employment_letter_context, seed_employment_letter_template,
        )
        from apps.accounts import services_employment_letter

        role = make_role(_unique('role'))
        employee = make_user(
            f'{_unique("emp")}@example.com', role=role, password='TestPass123!',
            full_name='Jane Doe', designation='Engineer', department='Technology',
            date_of_joining=datetime.date(2026, 1, 15),
        )

        template = seed_employment_letter_template()
        context = build_employment_letter_context(employee)
        rendered = render_template(template, context)

        self.assertIn(employee.full_name, rendered)
        self.assertIn(employee.designation, rendered)
        self.assertIn(employee.department, rendered)
        # Exact clause text, proven identical to the real reportlab generator's own logic.
        expected_clause = services_employment_letter._employment_status_statement(employee)
        self.assertIn(expected_clause, rendered)


class ConfigTransportTests(TestCase):
    def test_personal_data_guard_rejects_bad_model(self):
        from apps.accounts.models import EmployeeProfile
        with self.assertRaises(PersonalDataInRegistryError):
            assert_no_personal_data(EmployeeProfile)

    def test_seed_registry_registers_real_types(self):
        types = seed_registry()
        self.assertTrue(ConfigObjectType.objects.filter(code='PAY_COMPONENT').exists())
        self.assertTrue(ConfigObjectType.objects.filter(code='RATING_SCALE').exists())

    def test_export_dry_run_diff_create(self):
        seed_registry()
        PayComponent.objects.filter(code='TRANSPORT_TEST_COMP').delete()
        PayComponent.objects.create(code='TRANSPORT_TEST_COMP', name='Test', category=PayComponent.CATEGORY_EARNING, calculation_method=PayComponent.METHOD_FIXED)

        admin = _make_employee()
        package = export_package('Test Package', ['PAY_COMPONENT'], admin)
        PayComponent.objects.filter(code='TRANSPORT_TEST_COMP').delete()

        diff = dry_run_diff(package)
        matching = [o for o in diff['create'] if o['natural_key'] == {'code': 'TRANSPORT_TEST_COMP'}]
        self.assertEqual(len(matching), 1)

    def test_signature_tampering_detected(self):
        seed_registry()
        admin = _make_employee()
        RatingScale.objects.filter(code='TAMPER_TEST_SCALE').delete()
        RatingScale.objects.create(code='TAMPER_TEST_SCALE', name='Original', points=[{'value': 1, 'label': 'A'}])
        package = export_package('Test Package', ['RATING_SCALE'], admin)

        # Tamper with a real signed value after export — must be detected.
        package.contents['objects'][0]['fields']['name'] = 'Tampered Name'
        package.save(update_fields=['contents'])
        with self.assertRaises(SignatureInvalidError):
            dry_run_diff(package)

    def test_apply_and_rollback_round_trip(self):
        seed_registry()
        PayComponent.objects.filter(code='ROLLBACK_TEST_COMP').delete()
        admin = _make_employee()

        component = PayComponent.objects.create(
            code='ROLLBACK_TEST_COMP', name='Original Name',
            category=PayComponent.CATEGORY_EARNING, calculation_method=PayComponent.METHOD_FIXED,
        )
        package = export_package('Test Package', ['PAY_COMPONENT'], admin)
        component.name = 'Changed Locally Before Apply'
        component.save()

        package.status = ConfigPackage.STATUS_APPROVED
        package.approved_by = admin
        package.save(update_fields=['status', 'approved_by'])
        apply_package(package)

        component.refresh_from_db()
        self.assertEqual(component.name, 'Original Name')  # package's version won

        rollback_package(package)
        component.refresh_from_db()
        self.assertEqual(component.name, 'Changed Locally Before Apply')  # restored to pre-apply state

    def test_apply_requires_approved_status(self):
        seed_registry()
        admin = _make_employee()
        package = export_package('Test Package', ['RATING_SCALE'], admin)
        with self.assertRaises(ValueError):
            apply_package(package)

    def test_conflict_abort_raises(self):
        seed_registry()
        admin = _make_employee()
        PayComponent.objects.filter(code='CONFLICT_TEST_COMP').delete()
        component = PayComponent.objects.create(
            code='CONFLICT_TEST_COMP', name='Original',
            category=PayComponent.CATEGORY_EARNING, calculation_method=PayComponent.METHOD_FIXED,
        )
        package = export_package('Test Package', ['PAY_COMPONENT'], admin)
        component.name = 'Diverged'
        component.save()
        package.status = ConfigPackage.STATUS_APPROVED
        package.save(update_fields=['status'])

        key = f"PAY_COMPONENT:{{'code': 'CONFLICT_TEST_COMP'}}"
        with self.assertRaises(TransportConflictError):
            apply_package(package, resolve_conflicts={key: 'abort'})
