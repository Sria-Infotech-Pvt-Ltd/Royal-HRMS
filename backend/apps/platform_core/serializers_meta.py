from rest_framework import serializers

from apps.platform_core.models import EntityDefinition, FieldDefinition, FormLayout


class EntityDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntityDefinition
        fields = [
            'id', 'code', 'label', 'plural_label', 'description', 'module', 'kind',
            'app_label', 'model_name', 'attributes_column', 'icon', 'is_active',
            'has_attachments', 'history_enabled', 'number_series', 'title_template',
            'parent_entity', 'owner_field', 'legal_entity_scoped', 'status', 'version',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'version']


class FieldDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldDefinition
        fields = [
            'id', 'entity', 'code', 'label', 'help_text', 'placeholder', 'data_type',
            'is_core', 'is_system', 'required', 'default_value', 'multiple', 'lookup_type',
            'reference_entity', 'validation', 'is_sensitive', 'pii_category', 'is_unique',
            'unique_scope', 'is_searchable', 'is_filterable', 'is_sortable', 'is_exportable',
            'is_importable', 'applicability', 'status', 'version', 'order',
            'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        # Reuse the model's own clean() (sensitive-field exclusivity rule)
        # rather than re-deriving it here — build a throwaway instance with
        # existing values merged with the incoming ones so PATCH-partial
        # updates are validated against the full resulting state, not just
        # the fields present in this request.
        base = {f.name: getattr(self.instance, f.name) for f in FieldDefinition._meta.fields} if self.instance else {}
        base.update(attrs)
        base.pop('id', None)
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            FieldDefinition(**base).clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else str(exc))
        return attrs


class FormLayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormLayout
        fields = [
            'id', 'code', 'entity', 'context', 'name', 'legal_entity', 'country',
            'employment_type', 'priority', 'status', 'version', 'created_at', 'updated_at',
        ]
