from rest_framework import serializers
from .models import (
    PayrollSettings,
    StatutoryConfig,
    SalaryStructure,
    SalaryComponent,
    BranchPayrollConfig,
    EmployeeSalaryConfig,
    PayrollCycle,
    EmployeePayslip,
    PayslipQuery,
)


class PayrollSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollSettings
        fields = [
            'id',
            'cycle_start_day',
            'cycle_end_day',
            'pay_day',
            'approval_levels',
            'employee_query_window_hours',
            'enable_reimbursements',
            'enable_bonuses',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        start = data.get('cycle_start_day', getattr(self.instance, 'cycle_start_day', None))
        end = data.get('cycle_end_day', getattr(self.instance, 'cycle_end_day', None))
        pay = data.get('pay_day', getattr(self.instance, 'pay_day', None))
        for field, val in [('cycle_start_day', start), ('cycle_end_day', end), ('pay_day', pay)]:
            if val is not None and not (1 <= val <= 31):
                raise serializers.ValidationError({field: 'Must be between 1 and 31.'})
        return data


class StatutoryConfigSerializer(serializers.ModelSerializer):
    state_name = serializers.CharField(source='state.name', read_only=True)
    state_code = serializers.CharField(source='state.code', read_only=True)

    class Meta:
        model = StatutoryConfig
        fields = [
            'id',
            'state',
            'state_name',
            'state_code',
            'pt_applicable',
            'pt_slabs',
            'esi_applicable',
            'esi_wage_ceiling',
            'esi_employee_rate',
            'esi_employer_rate',
            'lwf_applicable',
            'lwf_employee_amount',
            'lwf_employer_amount',
            'lwf_frequency',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'state_name', 'state_code', 'created_at', 'updated_at']


class SalaryComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryComponent
        fields = [
            'id',
            'name',
            'component_type',
            'calculation_type',
            'value',
            'is_taxable',
            'is_active',
            'order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SalaryStructureSerializer(serializers.ModelSerializer):
    components = SalaryComponentSerializer(many=True, read_only=True)

    class Meta:
        model = SalaryStructure
        fields = [
            'id',
            'name',
            'description',
            'is_default',
            'is_active',
            'components',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SalaryStructureListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views — no nested components."""

    class Meta:
        model = SalaryStructure
        fields = ['id', 'name', 'description', 'is_default', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class BranchPayrollConfigSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.branch_name', read_only=True)
    branch_state = serializers.CharField(source='branch.state.name', read_only=True)
    structure_name = serializers.CharField(source='salary_structure.name', read_only=True)

    class Meta:
        model = BranchPayrollConfig
        fields = [
            'id',
            'branch',
            'branch_name',
            'branch_state',
            'salary_structure',
            'structure_name',
            'pf_applicable',
            'pf_employee_rate',
            'pf_employer_rate',
            'pf_wage_ceiling',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'branch_name', 'branch_state', 'structure_name', 'created_at', 'updated_at']


class EmployeeSalaryConfigSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id_code = serializers.CharField(source='employee.employee_id', read_only=True)
    structure_name = serializers.CharField(source='salary_structure.name', read_only=True)
    monthly_ctc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = EmployeeSalaryConfig
        fields = [
            'id',
            'employee',
            'employee_name',
            'employee_id_code',
            'annual_ctc',
            'monthly_ctc',
            'salary_structure',
            'structure_name',
            'effective_from',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'employee_name', 'employee_id_code',
            'structure_name', 'monthly_ctc', 'created_at', 'updated_at',
        ]


class PayrollCycleSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    l1_approver_name = serializers.CharField(
        source='attendance_approved_by_l1.full_name', read_only=True,
    )
    l2_approver_name = serializers.CharField(
        source='attendance_approved_by_l2.full_name', read_only=True,
    )
    payslip_count = serializers.SerializerMethodField()

    class Meta:
        model = PayrollCycle
        fields = [
            'id',
            'cycle_start',
            'cycle_end',
            'pay_date',
            'status',
            'created_by',
            'created_by_name',
            'attendance_approved_by_l1',
            'l1_approver_name',
            'attendance_approved_by_l2',
            'l2_approver_name',
            'attendance_l1_approved_at',
            'attendance_l2_approved_at',
            'query_window_closes_at',
            'paid_at',
            'notes',
            'payslip_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'created_by', 'created_by_name',
            'attendance_approved_by_l1', 'l1_approver_name',
            'attendance_approved_by_l2', 'l2_approver_name',
            'attendance_l1_approved_at', 'attendance_l2_approved_at',
            'query_window_closes_at', 'paid_at', 'payslip_count',
            'created_at', 'updated_at',
        ]

    def get_payslip_count(self, obj):
        return obj.payslips.count()


class EmployeePayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id_code = serializers.CharField(source='employee.employee_id', read_only=True)
    department = serializers.CharField(source='employee.department', read_only=True)
    branch = serializers.CharField(source='employee.branch', read_only=True)
    open_query_count = serializers.SerializerMethodField()

    class Meta:
        model = EmployeePayslip
        fields = [
            'id',
            'cycle',
            'employee',
            'employee_name',
            'employee_id_code',
            'department',
            'branch',
            'annual_ctc',
            'monthly_ctc',
            'basic',
            'hra',
            'special_allowance',
            'other_earnings',
            'reimbursements',
            'bonus',
            'gross_earnings',
            'total_working_days',
            'lop_days',
            'lop_deduction',
            'pf_employee',
            'pf_employer',
            'esi_employee',
            'esi_employer',
            'pt_deduction',
            'lwf_employee',
            'lwf_employer',
            'total_deductions',
            'net_pay',
            'status',
            'payslip_pdf',
            'sent_at',
            'query_deadline',
            'paid_at',
            'open_query_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'employee_name', 'employee_id_code', 'department', 'branch',
            'gross_earnings', 'lop_deduction', 'total_deductions', 'net_pay',
            'status', 'payslip_pdf', 'sent_at', 'query_deadline', 'paid_at',
            'open_query_count', 'created_at', 'updated_at',
        ]

    def get_open_query_count(self, obj):
        return obj.queries.filter(status=PayslipQuery.STATUS_OPEN).count()


class PayslipQuerySerializer(serializers.ModelSerializer):
    raised_by_name = serializers.CharField(source='raised_by.full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.full_name', read_only=True)

    class Meta:
        model = PayslipQuery
        fields = [
            'id',
            'payslip',
            'raised_by',
            'raised_by_name',
            'description',
            'status',
            'resolved_by',
            'resolved_by_name',
            'resolution_note',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'raised_by', 'raised_by_name', 'status',
            'resolved_by', 'resolved_by_name', 'created_at', 'updated_at',
        ]
