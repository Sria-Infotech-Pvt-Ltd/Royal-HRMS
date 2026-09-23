from rest_framework import serializers
from .models import (
    PayrollSettings,
    StatutoryConfig,
    SalaryStructure,
    SalaryComponent,
    BranchPayrollConfig,
    EmployeeSalaryConfig,
    PayrollCycle,
    ManagerAttendanceApproval,
    EmployeePayslip,
    PayslipQuery,
    PayrollAdjustment,
    EmployeeTaxDeclaration,
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
            'eps_rate',
            'edli_rate',
            'edli_wage_ceiling',
            'epf_admin_rate',
            # Exposed so the ESS payslip screen can show a real "Gratuity
            # provision" figure (basic * gratuity_rate / 100 — same formula
            # services_estimate.py already uses for the Hire wizard CTC
            # preview) instead of fabricating one. Gratuity itself is still
            # not persisted per payslip anywhere (see the model docstring),
            # so this stays a live estimate rather than a historical record.
            'gratuity_rate',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_eps_rate(self, value):
        if value is not None and not (0 < value <= 100):
            raise serializers.ValidationError('EPS rate must be between 0.01 and 100.')
        return value

    def validate_edli_rate(self, value):
        if value is not None and not (0 < value <= 100):
            raise serializers.ValidationError('EDLI rate must be between 0.01 and 100.')
        return value

    def validate_epf_admin_rate(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError('EPF admin rate must be between 0 and 100.')
        return value

    def validate_edli_wage_ceiling(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError('EDLI wage ceiling must be greater than 0.')
        return value

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
            'lwf_due_months',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'state_name', 'state_code', 'created_at', 'updated_at']

    def validate_lwf_due_months(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('lwf_due_months must be a list of month numbers.')
        for month in value:
            if not isinstance(month, int) or isinstance(month, bool) or not (1 <= month <= 12):
                raise serializers.ValidationError('Each due month must be an integer between 1 and 12.')
        if len(set(value)) != len(value):
            raise serializers.ValidationError('Due months must not contain duplicates.')
        return value

    def validate_esi_wage_ceiling(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('ESI wage ceiling cannot be negative.')
        return value

    def validate_esi_employee_rate(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError('ESI employee rate must be between 0 and 100.')
        return value

    def validate_esi_employer_rate(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError('ESI employer rate must be between 0 and 100.')
        return value

    def validate_lwf_employee_amount(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('LWF employee amount cannot be negative.')
        return value

    def validate_lwf_employer_amount(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('LWF employer amount cannot be negative.')
        return value

    def validate_pt_slabs(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('pt_slabs must be a list of slabs.')
        prev_min = None
        for i, slab in enumerate(value):
            if not isinstance(slab, dict):
                raise serializers.ValidationError(f'Slab {i + 1} must be an object with min/max/amount.')
            slab_min, slab_max, amount = slab.get('min'), slab.get('max'), slab.get('amount')
            if not isinstance(slab_min, (int, float)) or isinstance(slab_min, bool) or slab_min < 0:
                raise serializers.ValidationError(f'Slab {i + 1}: min must be a non-negative number.')
            if slab_max is not None and (not isinstance(slab_max, (int, float)) or isinstance(slab_max, bool)):
                raise serializers.ValidationError(f'Slab {i + 1}: max must be a number or left blank for no upper limit.')
            if slab_max is not None and slab_max <= slab_min:
                raise serializers.ValidationError(f'Slab {i + 1}: max must be greater than min.')
            if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount < 0:
                raise serializers.ValidationError(f'Slab {i + 1}: PT amount must be a non-negative number.')
            if prev_min is not None and slab_min < prev_min:
                raise serializers.ValidationError('Slabs must be ordered by ascending min.')
            prev_min = slab_min
        return value

    def validate(self, data):
        frequency = data.get('lwf_frequency', getattr(self.instance, 'lwf_frequency', StatutoryConfig.LWF_MONTHLY))
        due_months = data.get('lwf_due_months', getattr(self.instance, 'lwf_due_months', None) or [])
        if frequency == StatutoryConfig.LWF_ANNUAL and len(due_months) != 1:
            raise serializers.ValidationError({
                'lwf_due_months': 'Annual LWF requires exactly one due month.',
            })
        if frequency == StatutoryConfig.LWF_HALFYEARLY and len(set(due_months)) != 2:
            raise serializers.ValidationError({
                'lwf_due_months': 'Half-yearly LWF requires exactly two distinct due months.',
            })
        return data


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

    def _validate_rate(self, value, label):
        if value is None:
            return value
        if value < 0:
            raise serializers.ValidationError(f'{label} cannot be negative.')
        if value > 100:
            raise serializers.ValidationError(f'{label} cannot exceed 100%.')
        return value

    def validate_pf_employee_rate(self, value):
        return self._validate_rate(value, 'PF Employee Rate')

    def validate_pf_employer_rate(self, value):
        return self._validate_rate(value, 'PF Employer Rate')

    def validate_pf_wage_ceiling(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('PF Wage Ceiling cannot be negative.')
        return value


class EmployeeSalaryConfigSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id_code = serializers.CharField(source='employee.employee_id', read_only=True)
    structure_name = serializers.CharField(source='salary_structure.name', read_only=True)
    monthly_ctc = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    # Snapshot strings, not a nested serializer — a promotion record's own
    # designation/role fields are themselves already immutable snapshots
    # (see PromotionRecord's docstring), so echoing them back here needs no
    # extra query beyond the FK's own values.
    linked_promotion_designation = serializers.CharField(
        source='linked_promotion.new_designation', read_only=True, default=None,
    )
    linked_promotion_effective_date = serializers.DateField(
        source='linked_promotion.effective_date', read_only=True, default=None,
    )

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
            'reason',
            'reason_display',
            'reason_note',
            'linked_promotion',
            'linked_promotion_designation',
            'linked_promotion_effective_date',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'employee_name', 'employee_id_code',
            'structure_name', 'monthly_ctc', 'reason_display',
            'linked_promotion_designation', 'linked_promotion_effective_date',
            'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        # linked_promotion must belong to the same employee this config is
        # being assigned to — otherwise a crafted request could tag one
        # employee's CTC revision as "for" a completely different
        # employee's promotion.
        linked_promotion = attrs.get('linked_promotion')
        employee = attrs.get('employee') or getattr(self.instance, 'employee', None)
        if linked_promotion is not None and employee is not None and linked_promotion.employee_id != employee.id:
            raise serializers.ValidationError({
                'linked_promotion': "That promotion record doesn't belong to this employee.",
            })
        return attrs


class PayrollCycleSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    l1_approver_name = serializers.CharField(
        source='attendance_approved_by_l1.full_name', read_only=True,
    )
    l2_approver_name = serializers.CharField(
        source='attendance_approved_by_l2.full_name', read_only=True,
    )
    cancelled_by_name = serializers.CharField(source='cancelled_by.full_name', read_only=True)
    payslip_count = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source='branch.branch_name', read_only=True)

    class Meta:
        model = PayrollCycle
        fields = [
            'id',
            'cycle_start',
            'cycle_end',
            'pay_date',
            'status',
            'branch',
            'branch_name',
            'created_by',
            'created_by_name',
            'attendance_approved_by_l1',
            'l1_approver_name',
            'attendance_approved_by_l2',
            'l2_approver_name',
            'attendance_l1_approved_at',
            'attendance_l2_approved_at',
            'hr_self_approved_at',
            'query_window_closes_at',
            'paid_at',
            'cancelled_at',
            'cancelled_by',
            'cancelled_by_name',
            'cancellation_reason',
            'notes',
            'payslip_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'branch_name',
            'created_by', 'created_by_name',
            'attendance_approved_by_l1', 'l1_approver_name',
            'attendance_approved_by_l2', 'l2_approver_name',
            'attendance_l1_approved_at', 'attendance_l2_approved_at',
            'query_window_closes_at', 'paid_at',
            'cancelled_at', 'cancelled_by', 'cancelled_by_name', 'cancellation_reason',
            'payslip_count', 'created_at', 'updated_at',
        ]

    def get_payslip_count(self, obj):
        return obj.payslips.count()


class ManagerAttendanceApprovalSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source='manager.full_name', read_only=True)
    manager_email = serializers.CharField(source='manager.email', read_only=True)

    class Meta:
        model = ManagerAttendanceApproval
        fields = [
            'id',
            'cycle',
            'manager',
            'manager_name',
            'manager_email',
            'approved_at',
            'self_approved_at',
            'note',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'cycle', 'manager', 'manager_name', 'manager_email',
            'created_at', 'updated_at',
        ]


class EmployeePayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id_code = serializers.CharField(source='employee.employee_id', read_only=True)
    department = serializers.CharField(source='employee.department', read_only=True)
    branch = serializers.CharField(source='employee.branch', read_only=True)
    cycle_start = serializers.DateField(source='cycle.cycle_start', read_only=True)
    cycle_end = serializers.DateField(source='cycle.cycle_end', read_only=True)
    pay_date = serializers.DateField(source='cycle.pay_date', read_only=True)
    structure_name = serializers.CharField(source='salary_structure.name', read_only=True, default=None)
    open_query_count = serializers.SerializerMethodField()

    class Meta:
        model = EmployeePayslip
        fields = [
            'id',
            'cycle',
            'cycle_start',
            'cycle_end',
            'pay_date',
            'employee',
            'employee_name',
            'employee_id_code',
            'department',
            'branch',
            'salary_structure',
            'structure_name',
            'annual_ctc',
            'monthly_ctc',
            'basic',
            'hra',
            'special_allowance',
            'other_earnings',
            'reimbursements',
            'bonus',
            'bonus_breakdown',
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
            'income_tax',
            'adjustments_earning',
            'adjustments_deduction',
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
            'cycle_start', 'cycle_end', 'pay_date',
            'gross_earnings', 'lop_deduction', 'total_deductions', 'net_pay',
            'status', 'payslip_pdf', 'sent_at', 'query_deadline', 'paid_at',
            'open_query_count', 'created_at', 'updated_at',
        ]

    def get_open_query_count(self, obj):
        return obj.queries.filter(status=PayslipQuery.STATUS_OPEN).count()


class PayrollAdjustmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_id', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = PayrollAdjustment
        fields = (
            'id', 'employee', 'employee_name', 'employee_code',
            'month', 'type', 'label', 'amount',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_by', 'created_by_name', 'created_at', 'updated_at')

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero.')
        return value

    def validate_month(self, value):
        # Normalise to first of the month
        return value.replace(day=1)


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


class EmployeeTaxDeclarationSerializer(serializers.ModelSerializer):
    employee_name    = serializers.CharField(source='employee.full_name', read_only=True)
    tax_regime_display = serializers.CharField(source='get_tax_regime_display', read_only=True)
    status_display    = serializers.CharField(source='get_status_display', read_only=True)
    financial_year    = serializers.SerializerMethodField()
    approved_by_name  = serializers.SerializerMethodField()

    class Meta:
        model  = EmployeeTaxDeclaration
        fields = [
            'id', 'employee_name', 'financial_year_start', 'financial_year',
            'tax_regime', 'tax_regime_display', 'declared_investments',
            'status', 'status_display', 'submitted_at', 'approved_at', 'approved_by_name',
            'created_at', 'updated_at',
        ]

    def get_financial_year(self, obj: EmployeeTaxDeclaration) -> str:
        return f'{obj.financial_year_start}-{str(obj.financial_year_start + 1)[2:]}'

    def get_approved_by_name(self, obj: EmployeeTaxDeclaration) -> str:
        return obj.approved_by.full_name if obj.approved_by_id else ''


class EmployeeTaxDeclarationSaveSerializer(serializers.ModelSerializer):
    """Self-service create/update — only the fields the employee themselves
    controls. Submitting (status='submitted') is a separate explicit action
    (see EmployeeTaxDeclarationSubmitView) rather than a field on this
    serializer, so a plain PATCH can never accidentally lock in a
    declaration."""
    class Meta:
        model  = EmployeeTaxDeclaration
        fields = ['tax_regime', 'declared_investments']

    def validate_declared_investments(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('declared_investments must be an object of section -> amount.')
        for section, amount in value.items():
            try:
                if float(amount) < 0:
                    raise serializers.ValidationError(f'"{section}" amount cannot be negative.')
            except (TypeError, ValueError):
                raise serializers.ValidationError(f'"{section}" amount must be a number.')
        return value
