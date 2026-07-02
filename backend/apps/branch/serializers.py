from django.db import transaction
from rest_framework import serializers

from apps.branch.models import Branch, City, State
from apps.branch.utils import generate_branch_code


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

    def get_employees_count(self, obj):
        branch_counts = self.context.get('branch_counts')
        if branch_counts is not None:
            return branch_counts.get(obj.branch_name, 0)
        from apps.accounts.models import User
        return User.objects.filter(branch=obj.branch_name, is_active=True).count()

    class Meta:
        model = Branch
        fields = [
            'id', 'branch_code', 'branch_name', 'address',
            'state', 'state_name', 'city', 'city_name',
            'hr', 'hr_name',
            'employees_count', 'status', 'is_headquarter',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['branch_code', 'hr_name', 'employees_count', 'created_at', 'updated_at']

    def validate_address(self, value: str) -> str:
        if value is not None:
            value = value.strip()
        if not value:
            raise serializers.ValidationError('Branch address is required.')
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
            raise serializers.ValidationError('Branch name must not be blank.')
        if len(value) > 200:
            raise serializers.ValidationError('Branch name must be under 200 characters.')
        return value

    def validate(self, data):
        city  = data.get('city')  or (self.instance.city  if self.instance else None)
        state = data.get('state') or (self.instance.state if self.instance else None)
        if city and state and city.state_id != state.pk:
            raise serializers.ValidationError(
                {'city': 'Selected city does not belong to the selected state.'}
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
