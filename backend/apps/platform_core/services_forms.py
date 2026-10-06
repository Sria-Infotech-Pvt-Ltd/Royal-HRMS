"""Phase 2 Task D.4 — form layout resolution."""
from __future__ import annotations

from apps.platform_core import cache as metadata_cache
from apps.platform_core.models import FormLayout


def resolve_layout(entity, context: str, *, user=None, record=None, country=None, legal_entity=None, employment_type=None) -> dict:
    """Returns the effective PUBLISHED layout for (entity, context) as a
    plain dict ready to serialize to the frontend. Most-specific-match
    wins by `priority` among layouts whose applicability (legal_entity/
    country/employment_type) matches, falling back to the
    least-specific (no applicability set) published layout."""
    suffix = f'{entity.code}:{context}:{getattr(legal_entity, "pk", legal_entity) or "-"}:{getattr(country, "pk", country) or "-"}:{employment_type or "-"}'

    def _load():
        qs = FormLayout.objects.filter(entity=entity, context=context, status=FormLayout.STATUS_PUBLISHED)
        candidates = list(qs.prefetch_related('steps__sections__placements__field'))
        matching = []
        for layout in candidates:
            if layout.legal_entity_id and legal_entity and str(layout.legal_entity_id) != str(getattr(legal_entity, 'pk', legal_entity)):
                continue
            if layout.country_id and country and str(layout.country_id) != str(getattr(country, 'pk', country)):
                continue
            if layout.employment_type and employment_type and layout.employment_type != employment_type:
                continue
            matching.append(layout)
        if not matching:
            return None
        best = max(matching, key=lambda l: l.priority)
        return _serialize_layout(best)

    return metadata_cache.cached('lookups', f'layout:{suffix}', _load)


def _serialize_layout(layout: FormLayout) -> dict:
    steps = []
    for step in layout.steps.all().order_by('order'):
        sections = []
        for section in step.sections.all().order_by('order'):
            placements = []
            for placement in section.placements.all().order_by('order'):
                field = placement.field
                placements.append({
                    'field_code': field.code,
                    'data_type': field.data_type,
                    'label': placement.label_override or field.label,
                    'help_text': placement.help_override or field.help_text,
                    'order': placement.order,
                    'column_span': placement.column_span,
                    'read_only': placement.read_only,
                    'visible_when': placement.visible_when,
                    'required_when': placement.required_when,
                    'required': field.required,
                    'multiple': field.multiple,
                    'lookup_type_code': field.lookup_type.code if field.lookup_type else None,
                    'validation': field.validation,
                })
            sections.append({
                'label': section.label, 'order': section.order, 'columns': section.columns,
                'collapsible': section.collapsible, 'visible_when': section.visible_when,
                'repeats_for_entity': section.repeats_for_entity.code if section.repeats_for_entity else None,
                'placements': placements,
            })
        steps.append({'label': step.label, 'icon': step.icon, 'order': step.order, 'visible_when': step.visible_when, 'sections': sections})

    return {
        'layout_code': layout.code, 'layout_version': layout.version, 'entity_code': layout.entity.code,
        'context': layout.context, 'steps': steps,
    }


def validate_submission(entity, context: str, values: dict, *, legal_entity=None, country=None, employment_type=None) -> dict:
    """Server-side form validation (Task D.6): required / required_when /
    type rules from the RESOLVED layout, in ADDITION to (never instead
    of) whatever serializer validation already runs for this context."""
    from apps.platform_core import services_conditions as conditions
    from apps.platform_core import services_datatypes as datatypes
    from apps.platform_core.models import FieldDefinition

    layout = resolve_layout(entity, context, legal_entity=legal_entity, country=country, employment_type=employment_type)
    if layout is None:
        return {}

    errors = {}
    field_defs_by_code = {f.code: f for f in FieldDefinition.objects.filter(entity=entity)}
    for step in layout['steps']:
        for section in step['sections']:
            for placement in section['placements']:
                code = placement['field_code']
                value = values.get(code)
                required_when = placement['required_when'] or {}
                # See services_attributes.validate()'s identical comment —
                # an empty required_when must not be treated as "always
                # required" even though conditions.evaluate({}) is True.
                is_required = placement['required'] or (bool(required_when) and conditions.evaluate(required_when, values))
                if is_required and value in (None, '', []):
                    errors[code] = 'This field is required.'
                    continue
                if value not in (None, '', []) and code in field_defs_by_code:
                    try:
                        datatypes.validate_and_normalise(field_defs_by_code[code], value)
                    except datatypes.DataTypeError as exc:
                        errors[code] = exc.message
    return errors
