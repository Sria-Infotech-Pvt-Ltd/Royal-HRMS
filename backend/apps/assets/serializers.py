from rest_framework import serializers

from apps.assets.models import Asset, AssetAssignment, AssetCategory, AssetMaintenanceRecord, AssetType

OTHER = 'Other'


class AssetCategorySerializer(serializers.ModelSerializer):
    """Mirrors DepartmentSerializer's exact validation shape (accounts/serializers.py)."""

    class Meta:
        model = AssetCategory
        fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Category name is required.')
        if len(value) > 100:
            raise serializers.ValidationError('Category name must be under 100 characters.')
        return value

    def validate(self, attrs: dict) -> dict:
        name = attrs.get('name', getattr(self.instance, 'name', None))
        qs = AssetCategory.objects.filter(name__iexact=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({'name': f'A category named "{name}" already exists.'})
        return attrs


class AssetTypeSerializer(serializers.ModelSerializer):
    """Mirrors DesignationSerializer's exact validation shape (name+parent unique together)."""
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = AssetType
        fields = ['id', 'name', 'category', 'category_name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'category_name', 'created_at', 'updated_at']

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Asset Type name is required.')
        if len(value) > 100:
            raise serializers.ValidationError('Asset Type name must be under 100 characters.')
        return value

    def validate_category(self, value):
        if value is None:
            raise serializers.ValidationError('Category is required.')
        return value

    def validate(self, attrs: dict) -> dict:
        name = attrs.get('name', getattr(self.instance, 'name', None))
        category = attrs.get('category', getattr(self.instance, 'category', None))
        if category is None:
            raise serializers.ValidationError({'category': 'Category is required.'})
        qs = AssetType.objects.filter(name__iexact=name, category=category)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'name': f'An asset type named "{name}" already exists in this category.'}
            )
        return attrs


class AssetSerializer(serializers.ModelSerializer):
    branch_name       = serializers.CharField(source='branch.branch_name', read_only=True)
    status_display    = serializers.CharField(source='get_status_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    created_by_name    = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    active_maintenance = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            'id', 'asset_tag', 'asset_name', 'category', 'category_other',
            'asset_type', 'asset_type_other', 'brand', 'model',
            'serial_number', 'purchase_date', 'purchase_price', 'vendor',
            'warranty_start_date', 'warranty_end_date',
            'branch', 'branch_name', 'status', 'status_display', 'condition', 'condition_display',
            'description', 'created_by_name', 'active_maintenance', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'branch_name', 'status_display', 'condition_display',
            'created_by_name', 'active_maintenance', 'created_at', 'updated_at',
        ]

    def get_active_maintenance(self, obj: Asset) -> dict | None:
        # Relies on the view's queryset prefetching `_active_maintenance`
        # (see views.py) to avoid an N+1 query per row on the list endpoint;
        # falls back to a direct query so this serializer still works
        # correctly (just less efficiently) if ever used without that
        # prefetch — e.g. AssetAssignmentSerializer-adjacent call sites.
        records = getattr(obj, '_active_maintenance', None)
        if records is None:
            records = list(obj.maintenance_records.filter(status=AssetMaintenanceRecord.STATUS_IN_PROGRESS)[:1])
        if not records:
            return None
        record = records[0]
        return {
            'id': str(record.pk),
            'maintenance_start_date': record.maintenance_start_date,
            'issue': record.issue,
            'expected_completion_date': record.expected_completion_date,
            'vendor': record.vendor,
        }

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

        # ── Category / Asset Type master-data + "Other" handling ──────────
        # A submitted value must match an active master-data name, UNLESS
        # it's identical to what this asset already had (tolerates legacy
        # free-text rows that predate the master-data feature — spec:
        # "handle it safely instead of silently changing existing data").
        category = _resolve('category')
        prior_category = getattr(self.instance, 'category', None) if self.instance else None
        if category and category != OTHER and category != prior_category:
            if not AssetCategory.objects.filter(name__iexact=category, is_active=True).exists():
                raise serializers.ValidationError(
                    {'category': f'"{category}" is not a valid category. Add it in Asset Categories first.'}
                )

        asset_type = _resolve('asset_type')
        prior_asset_type = getattr(self.instance, 'asset_type', None) if self.instance else None
        if asset_type and asset_type != OTHER and asset_type != prior_asset_type:
            type_qs = AssetType.objects.filter(name__iexact=asset_type, is_active=True)
            if category:
                type_qs = type_qs.filter(category__name__iexact=category)
            if not type_qs.exists():
                raise serializers.ValidationError(
                    {'asset_type': f'"{asset_type}" is not a valid type for category "{category}".'}
                )

        # "Other" custom values: required (non-blank, non-whitespace) when
        # the master value is "Other"; cleared otherwise so a stale custom
        # value never lingers once the user picks a real category/type —
        # never overwrites the master value itself, only this side field.
        category_other = (attrs.get('category_other') or '').strip()
        if category == OTHER:
            if not category_other:
                raise serializers.ValidationError(
                    {'category_other': 'Enter a custom category name when Category is "Other".'}
                )
            attrs['category_other'] = category_other
        elif 'category' in attrs or 'category_other' in attrs:
            attrs['category_other'] = ''

        asset_type_other = (attrs.get('asset_type_other') or '').strip()
        if asset_type == OTHER:
            if not asset_type_other:
                raise serializers.ValidationError(
                    {'asset_type_other': 'Enter a custom asset type when Asset Type is "Other".'}
                )
            attrs['asset_type_other'] = asset_type_other
        elif 'asset_type' in attrs or 'asset_type_other' in attrs:
            attrs['asset_type_other'] = ''

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


class AssetMaintenanceRecordSerializer(serializers.ModelSerializer):
    """Read-only — a row in an asset's maintenance history."""
    asset_tag               = serializers.CharField(source='asset.asset_tag', read_only=True)
    status_display          = serializers.CharField(source='get_status_display', read_only=True)
    outcome_display          = serializers.CharField(source='get_outcome_display', read_only=True, default='')
    sent_to_maintenance_by_name = serializers.CharField(
        source='sent_to_maintenance_by.full_name', read_only=True, default=None,
    )
    completed_by_name = serializers.CharField(source='completed_by.full_name', read_only=True, default=None)

    class Meta:
        model = AssetMaintenanceRecord
        fields = [
            'id', 'asset', 'asset_tag', 'status', 'status_display',
            'maintenance_start_date', 'issue', 'expected_completion_date', 'vendor', 'estimated_cost',
            'notes', 'sent_to_maintenance_by', 'sent_to_maintenance_by_name',
            'completed_date', 'outcome', 'outcome_display', 'maintenance_notes', 'actual_cost',
            'completed_by', 'completed_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class SendToMaintenanceSerializer(serializers.Serializer):
    """Input validation for POST /assets/<pk>/send-to-maintenance/."""
    maintenance_start_date   = serializers.DateField(required=True)
    issue                     = serializers.CharField(required=True, allow_blank=False)
    expected_completion_date = serializers.DateField(required=False, allow_null=True)
    vendor                    = serializers.CharField(required=False, allow_blank=True, default='')
    estimated_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=0,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_issue(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Issue / Reason is required.')
        return value

    def validate(self, attrs: dict) -> dict:
        start = attrs.get('maintenance_start_date')
        expected = attrs.get('expected_completion_date')
        if start and expected and expected < start:
            raise serializers.ValidationError(
                {'expected_completion_date': 'Expected completion date cannot be before the start date.'}
            )
        return attrs


class CompleteMaintenanceSerializer(serializers.Serializer):
    """Input validation for POST /assets/maintenance/<pk>/complete/."""
    completed_date      = serializers.DateField(required=True)
    outcome               = serializers.ChoiceField(choices=AssetMaintenanceRecord.OUTCOME_CHOICES, required=True)
    maintenance_notes    = serializers.CharField(required=True, allow_blank=False)
    actual_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=0,
    )
    # Only meaningful (and only ever applied) when outcome == repaired —
    # lets HR record the asset's actual post-repair condition rather than
    # this view guessing one; ignored otherwise (a not-repairable asset is
    # retired, its condition no longer matters for assignment purposes).
    resulting_condition = serializers.ChoiceField(choices=Asset.CONDITION_CHOICES, required=False)

    def validate_maintenance_notes(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Repair/Maintenance notes are required.')
        return value

    def validate(self, attrs: dict) -> dict:
        record = self.context.get('record')
        completed_date = attrs.get('completed_date')
        if record and completed_date and completed_date < record.maintenance_start_date:
            raise serializers.ValidationError(
                {'completed_date': 'Completed date cannot be before the maintenance start date.'}
            )
        return attrs
