from rest_framework import serializers

from apps.platform_core.models import (
    Policy, PolicyAssignment, PolicyType, RuleDefinition, RuleTable, RuleTableVersion, RuleTestCase, RuleVersion,
)


class RuleDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleDefinition
        fields = [
            'id', 'code', 'name', 'description', 'module', 'purpose',
            'input_context', 'return_type', 'expression', 'status', 'version',
            'published_at', 'published_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'version', 'published_at', 'published_by']


class RuleTestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleTestCase
        fields = ['id', 'rule', 'name', 'inputs', 'expected_output', 'last_result', 'last_run_at', 'passed']
        read_only_fields = ['last_result', 'last_run_at', 'passed']


class RuleVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleVersion
        fields = ['id', 'rule', 'version', 'expression', 'input_context', 'return_type', 'effective_from', 'published_at', 'published_by']


class RuleTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleTable
        fields = ['id', 'code', 'description', 'columns', 'created_at', 'updated_at']


class RuleTableVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleTableVersion
        fields = ['id', 'table', 'rows', 'effective_from', 'effective_to', 'legal_entity', 'country']


class PolicyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyType
        fields = ['id', 'code', 'name', 'module', 'parameter_schema', 'resolution_strategy', 'specificity_order', 'is_system']


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = [
            'id', 'type', 'code', 'name', 'description', 'parameters', 'version',
            'status', 'effective_from', 'effective_to', 'legal_entity', 'is_default',
            'created_at', 'updated_at',
        ]


class PolicyAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyAssignment
        fields = [
            'id', 'policy', 'target_type', 'target_id', 'include_children',
            'condition', 'effective_from', 'effective_to', 'priority',
        ]
