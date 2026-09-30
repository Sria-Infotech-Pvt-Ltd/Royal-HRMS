from rest_framework import serializers

from apps.assets.models import Asset, AssetAssignment


class AssetSerializer(serializers.ModelSerializer):
    branch_name       = serializers.CharField(source='branch.branch_name', read_only=True)
    status_display    = serializers.CharField(source='get_status_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    created_by_name    = serializers.CharField(source='created_by.full_name', read_only=True, default=None)

    class Meta:
        model = Asset
        fields = [
            'id', 'asset_tag', 'asset_name', 'category', 'asset_type', 'brand', 'model',
            'serial_number', 'purchase_date', 'purchase_price', 'vendor',
            'warranty_start_date', 'warranty_end_date',
            'branch', 'branch_name', 'status', 'status_display', 'condition', 'condition_display',
            'description', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'branch_name', 'status_display', 'condition_display',
            'created_by_name', 'created_at', 'updated_at',
        ]

    def validate_asset_tag(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Asset Tag is required.')
        return value

    def validate_asset_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Asset Name is required.')
        return value

    def validate_category(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Category is required.')
        return value

    def validate_asset_type(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Asset Type is required.')
        return value

    def validate_serial_number(self, value):
        # Blank -> None so multiple assets with no serial number don't
        # collide against the DB unique constraint (NULL != NULL there).
        value = (value or '').strip()
        return value or None

    def validate(self, attrs: dict) -> dict:
        def _resolve(field):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, None) if self.instance else None

        start = _resolve('warranty_start_date')
        end   = _resolve('warranty_end_date')
        if start and end and end < start:
            raise serializers.ValidationError(
                {'warranty_end_date': 'Warranty end date cannot be before the start date.'}
            )

        # Uniqueness checked explicitly here (not left to a DB IntegrityError)
        # so both collisions return the same field-level-error shape the
        # frontend already knows how to render — matches
        # DesignationSerializer.validate's own convention (accounts/serializers.py).
        asset_tag = _resolve('asset_tag')
        if asset_tag:
            qs = Asset.objects.filter(asset_tag__iexact=asset_tag)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'asset_tag': f'Asset Tag "{asset_tag}" already exists.'}
                )

        serial_number = _resolve('serial_number')
        if serial_number:
            qs = Asset.objects.filter(serial_number__iexact=serial_number)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'serial_number': f'Serial Number "{serial_number}" already exists.'}
                )

        return attrs


class AssetAssignmentSerializer(serializers.ModelSerializer):
    """Read-only — a row in an employee's (or an asset's) assignment history."""
    asset_tag         = serializers.CharField(source='asset.asset_tag', read_only=True)
    asset_name        = serializers.CharField(source='asset.asset_name', read_only=True)
    asset_type        = serializers.CharField(source='asset.asset_type', read_only=True)
    serial_number     = serializers.CharField(source='asset.serial_number', read_only=True)
    employee_name     = serializers.CharField(source='employee.full_name', read_only=True)
    assigned_by_name  = serializers.CharField(source='assigned_by.full_name', read_only=True, default=None)
    returned_by_name  = serializers.CharField(source='returned_by.full_name', read_only=True, default=None)
    status_display    = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AssetAssignment
        fields = [
            'id', 'asset', 'asset_tag', 'asset_name', 'asset_type', 'serial_number',
            'employee', 'employee_name', 'status', 'status_display',
            'assigned_date', 'condition_at_assignment', 'expected_return_date',
            'assign_remarks', 'assigned_by', 'assigned_by_name',
            'return_date', 'return_condition', 'return_reason', 'return_remarks',
            'returned_by', 'returned_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class AssignAssetSerializer(serializers.Serializer):
    """Input validation for POST /assets/employees/<employee_id>/assign/."""
    asset                    = serializers.PrimaryKeyRelatedField(queryset=Asset.objects.all())
    assigned_date            = serializers.DateField(required=True)
    condition_at_assignment  = serializers.ChoiceField(choices=Asset.CONDITION_CHOICES, required=True)
    expected_return_date     = serializers.DateField(required=False, allow_null=True)
    remarks                  = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_asset(self, value: Asset) -> Asset:
        if value.status != Asset.STATUS_AVAILABLE:
            raise serializers.ValidationError(
                f'"{value.asset_tag}" is not available — current status: {value.get_status_display()}.'
            )
        return value

    def validate(self, attrs: dict) -> dict:
        start = attrs.get('assigned_date')
        expected_return = attrs.get('expected_return_date')
        if start and expected_return and expected_return < start:
            raise serializers.ValidationError(
                {'expected_return_date': 'Expected return date cannot be before the assigned date.'}
            )
        return attrs


class ReturnAssetSerializer(serializers.Serializer):
    """Input validation for POST /assets/assignments/<assignment_id>/return/."""
    return_date      = serializers.DateField(required=True)
    return_condition = serializers.ChoiceField(choices=Asset.CONDITION_CHOICES, required=True)
    return_reason    = serializers.CharField(required=True, allow_blank=False)
    remarks          = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_return_reason(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Return reason is required.')
        return value

    def validate(self, attrs: dict) -> dict:
        assignment = self.context.get('assignment')
        return_date = attrs.get('return_date')
        if assignment and return_date and return_date < assignment.assigned_date:
            raise serializers.ValidationError(
                {'return_date': 'Return date cannot be before the assignment date.'}
            )
        return attrs
