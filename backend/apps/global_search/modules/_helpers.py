from __future__ import annotations

from django.db.models import Model


def choices_of(model: type[Model], field_name: str) -> tuple[tuple[str, str], ...]:
    """The (stored value, label) choices a model field already declares, so the registry never repeats them."""
    return tuple((str(value), str(label)) for value, label in model._meta.get_field(field_name).choices)


def label_of(obj: Model, field_name: str) -> str:
    """The readable label of a choice field, or '' when empty."""
    return getattr(obj, f'get_{field_name}_display')() if getattr(obj, field_name, '') else ''


def short_date(value) -> str:
    """DD-MM-YYYY, the format used everywhere in the app; '' for nothing."""
    return value.strftime('%d-%m-%Y') if value else ''
