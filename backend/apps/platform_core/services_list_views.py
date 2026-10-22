"""Phase 2 Task G — list view resolution and query execution.

Column definitions are presentation metadata (which fields, what order,
what label) — the actual masking/permission enforcement for each column's
VALUE still goes through services_attributes.read() exactly like any
other attribute read, so a list view can never show more than a direct
record read already would.
"""
from __future__ import annotations

from apps.platform_core.models import FieldDefinition, ListViewDefinition


class ListViewError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def resolve_default_view(entity, user) -> ListViewDefinition | None:
    """Personal default (if the user saved one) beats a position default,
    which beats the system default — most-specific-to-the-user wins,
    same precedence direction as Phase 1's feature-flag overrides."""
    qs = ListViewDefinition.objects.filter(entity=entity, is_default=True)

    personal = qs.filter(visibility=ListViewDefinition.VISIBILITY_PERSONAL, owner=user).first()
    if personal:
        return personal

    from core.access import current_seat

    seat = current_seat(user)
    if seat is not None:
        position_view = qs.filter(visibility=ListViewDefinition.VISIBILITY_POSITION, position_id=seat.pk).first()
        if position_view:
            return position_view

    return qs.filter(visibility=ListViewDefinition.VISIBILITY_SYSTEM).first()


def list_views_for_user(entity, user):
    from django.db.models import Q
    qs = ListViewDefinition.objects.filter(entity=entity)
    from core.access import current_seat

    seat = current_seat(user)
    visible = Q(visibility=ListViewDefinition.VISIBILITY_SYSTEM)
    if seat is not None:
        visible |= Q(visibility=ListViewDefinition.VISIBILITY_POSITION, position_id=seat.pk)
    visible |= Q(visibility=ListViewDefinition.VISIBILITY_PERSONAL, owner=user)
    return qs.filter(visible)


def validate_columns(entity, columns: list, *, sort_field: str | None = None) -> None:
    """Task G.3 — a column referencing a sensitive field is allowed (it
    will simply render masked, same as any other sensitive read); a
    non-sortable field used as the sort key is rejected outright."""
    field_defs = {f.code: f for f in FieldDefinition.objects.filter(entity=entity)}
    for col in columns:
        code = col.get('field')
        if code and code not in field_defs and not _is_core_column(entity, code):
            raise ListViewError(f'Unknown column field: {code}')

    if sort_field:
        bare = sort_field.lstrip('-')
        field_def = field_defs.get(bare)
        if field_def is not None and not field_def.is_sortable:
            raise ListViewError(f'Field "{bare}" is not sortable.')


def _is_core_column(entity, code: str) -> bool:
    """A column may also reference a real model column (not a custom
    FieldDefinition) on a core entity, e.g. "branch_name" on Branch —
    those aren't registered in FieldDefinition at all in this phase, so
    they're accepted here without further checking (the serializer for
    that core entity's own detail/list endpoint already validates them)."""
    return entity.kind == entity.KIND_CORE


def build_view_payload(view: ListViewDefinition) -> dict:
    return {
        'code': view.code, 'name': view.name, 'columns': view.columns,
        'default_filters': view.default_filters, 'default_sort': view.default_sort,
        'visibility': view.visibility, 'is_default': view.is_default,
    }


def execute_custom_entity_query(entity, *, filters: dict, sort: str | None, for_user):
    """Task G.4 — only ever touches `is_filterable`/`is_sortable` fields;
    anything else raises rather than silently being ignored or executed
    unsafely. Returns a queryset of CustomRecord — callers serialize rows
    via services_custom_objects.read_record()/list_records() exactly like
    the generic data API does, so masking/exclusion stays centralised."""
    from apps.platform_core import services_custom_objects as custom_objects

    field_defs = {f.code: f for f in FieldDefinition.objects.filter(entity=entity)}
    qs = custom_objects.list_records(entity)

    for code, value in (filters or {}).items():
        field_def = field_defs.get(code)
        if field_def is None or not field_def.is_filterable:
            raise ListViewError(f'Field "{code}" is not filterable.')
        qs = qs.filter(**{f'data__{code}': value})

    if sort:
        bare = sort.lstrip('-')
        field_def = field_defs.get(bare)
        if field_def is not None and not field_def.is_sortable:
            raise ListViewError(f'Field "{bare}" is not sortable.')
        if bare in field_defs:
            qs = qs.order_by(('-' if sort.startswith('-') else '') + f'data__{bare}')
        else:
            qs = qs.order_by(sort)

    return qs
