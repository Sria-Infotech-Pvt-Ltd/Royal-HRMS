import re

from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import CompanyGSTRegistration
from apps.branch.models import Branch, City, EmployeeBranchAccess, State
from apps.branch.utils import generate_branch_code

_BRANCH_NAME_RE = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9 &\-.]*[A-Za-z0-9])?$')
_CITY_NAME_RE   = re.compile(r"^[A-Za-z]+(?:[ '\-][A-Za-z]+)*$")


class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ['id', 'name', 'code', 'is_active']


class CitySerializer(serializers.ModelSerializer):
    state_name = serializers.CharField(source='state.name', read_only=True)

    class Meta:
        model = City
        fields = ['id', 'name', 'state', 'state_name', 'is_active']


class BranchSerializer(serializers.ModelSerializer):
    state_name = serializers.CharField(source='state.name', read_only=True)
    city_name  = serializers.CharField(source='city.name', read_only=True)
    hr_name    = serializers.CharField(source='hr.full_name', read_only=True, default=None)
    employees_count = serializers.SerializerMethodField()
    has_coordinates = serializers.BooleanField(read_only=True)

    city = serializers.PrimaryKeyRelatedField(queryset=City.objects.all(), required=False)
    # Fallback for a city that isn't in the City dropdown yet — get-or-created under
    # the selected state instead of requiring `city` to already exist.
    new_city_name = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=100)

    gst_registration      = serializers.PrimaryKeyRelatedField(
        queryset=CompanyGSTRegistration.objects.all(), required=False, allow_null=True,
    )
    gst_registration_gstin = serializers.CharField(source='gst_registration.gstin', read_only=True, default=None)

    def get_employees_count(self, obj):
        branch_counts = self.context.get('branch_counts')
        if branch_counts is not None:
            # Keyed by Branch PK now, not branch_name — see the view's own
            # comment on where branch_counts is built (apps/branch/views.py).
            return branch_counts.get(obj.pk, 0)
        # branch_fk, not the legacy branch=obj.branch_name string comparison —
        # see User.branch_fk's docstring (apps/accounts/models.py). This is
        # the first call site converted; branch=obj.branch_name misses any
        # employee whose branch string doesn't exactly match (a stale/typo'd
        # value — confirmed via the 0133 backfill migration's own report that
        # such rows exist in this exact dataset).
        return obj.employees.filter(is_active=True).count()

    class Meta:
        model = Branch
        fields = [
            'id', 'branch_code', 'branch_name', 'address',
            'state', 'state_name', 'city', 'city_name', 'new_city_name',
            'hr', 'hr_name',
            'gst_registration', 'gst_registration_gstin',
            'employees_count', 'status', 'is_headquarter',
            'latitude', 'longitude', 'allowed_radius_meters', 'geofencing_enabled',
            'has_coordinates',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['branch_code', 'hr_name', 'employees_count', 'has_coordinates', 'created_at', 'updated_at']

    def validate_address(self, value: str) -> str:
        if value is not None:
            value = value.strip()
        if not value:
            raise serializers.ValidationError('Company Code address is required.')
        if len(value) > 500:
            raise serializers.ValidationError('Address must be 500 characters or fewer.')
        return value

    def validate_status(self, value: str) -> str:
        valid = [choice[0] for choice in Branch.STATUS_CHOICES]
        if value not in valid:
            raise serializers.ValidationError(
                f'Status must be one of: {", ".join(valid)}.'
            )
        return value

    def validate_branch_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Company Code name must not be blank.')
        if len(value) > 200:
            raise serializers.ValidationError('Company Code name must be under 200 characters.')
        if not _BRANCH_NAME_RE.match(value):
            raise serializers.ValidationError(
                'Company Code name may only contain letters, numbers, spaces, & - and . characters.'
            )
        return value

    def validate(self, data):
        state = data.get('state') or (self.instance.state if self.instance else None)
        new_city_name = data.pop('new_city_name', '').strip()

        if not data.get('city') and new_city_name:
            if not _CITY_NAME_RE.match(new_city_name):
                raise serializers.ValidationError(
                    {'new_city_name': 'City name may only contain letters, spaces, hyphens and apostrophes.'}
                )
            if not state:
                raise serializers.ValidationError({'city': 'Select a state before entering a new city.'})
            city, _ = City.objects.get_or_create(
                name=new_city_name, state=state, defaults={'is_active': True},
            )
            data['city'] = city

        city = data.get('city') or (self.instance.city if self.instance else None)
        if not city:
            raise serializers.ValidationError({'city': 'City is required.'})
        if state and city.state_id != state.pk:
            raise serializers.ValidationError(
                {'city': 'Selected city does not belong to the selected state.'}
            )

        gst_registration = data.get('gst_registration', getattr(self.instance, 'gst_registration', None))
        if gst_registration and state and gst_registration.state != state.name:
            raise serializers.ValidationError(
                {'gst_registration': f'This GST registration is for {gst_registration.state}, not {state.name}.'}
            )

        # Geofencing: enabling requires coordinates either in this request or already on the branch
        enabled = data.get('geofencing_enabled')
        if enabled:
            lat = data.get('latitude') or (self.instance.latitude if self.instance else None)
            lon = data.get('longitude') or (self.instance.longitude if self.instance else None)
            if lat is None or lon is None:
                raise serializers.ValidationError(
                    {'geofencing_enabled': 'Set latitude and longitude before enabling geofencing.'}
                )

        return data

    def create(self, validated_data):
        city = validated_data['city']
        with transaction.atomic():
            branch_code = generate_branch_code(city.name)
            return Branch.objects.create(branch_code=branch_code, **validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class EmployeeBranchAccessSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_id', read_only=True)
    branch_name   = serializers.CharField(source='branch.branch_name', read_only=True)
    branch_code   = serializers.CharField(source='branch.branch_code', read_only=True)

    class Meta:
        model  = EmployeeBranchAccess
        fields = [
            'id', 'employee', 'employee_name', 'employee_code',
            'branch', 'branch_name', 'branch_code', 'is_primary',
            'created_at',
        ]
        read_only_fields = [
            'id', 'created_at',
            'employee_name', 'employee_code', 'branch_name', 'branch_code',
        ]
