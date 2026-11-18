"""The searchable-field registry: the ONE list of what global search may look at.

Each module declares its own scoped queryset, the permission that opens it, and every field a person may search or filter by.
A field that is not declared here cannot be searched, filtered, shown or exported: that is the allow-list. Fields that need more
than the module permission (personal or financial data) name the extra permission, and are removed for viewers who lack it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from django.db.models import Q, QuerySet

from core.permissions import has_perm


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    type: str
    path: str                                   # the real ORM path; never sent to or accepted from the browser
    choices: tuple[tuple[str, str], ...] = ()
    searchable: bool = False                    # included in the free-text search box
    permission: str | None = None               # extra permission needed to use this field at all
    operators: tuple[str, ...] = ()             # overrides the type's default operators
    build: Callable[[str, object], Q] | None = None   # custom filter for derived fields: (positive operator, value) -> Q
    show: bool = True                           # listed in the registry sent to the filter builder

    def usable_by(self, user) -> bool:
        return self.permission is None or has_perm(user, self.permission)


@dataclass(frozen=True)
class SearchModule:
    key: str
    label: str
    icon: str                                   # Tabler icon name
    queryset: Callable[[object], QuerySet]      # the viewer's scoped rows, built from the module's own existing visibility rule
    fields: tuple[FieldSpec, ...]
    describe: Callable[[object], dict]          # one row -> {"id", "title", "subtitle", "meta": {...}, "url"}; explicit fields only
    permission: str | None = None               # needed to search the module at all (None: every signed-in person, own scope)
    order_by: tuple[str, ...] = ('-pk',)
    default_url: str = ''
    by_key: dict = field(default_factory=dict, compare=False)

    def __post_init__(self):
        object.__setattr__(self, 'by_key', {spec.key: spec for spec in self.fields})

    def is_open_to(self, user) -> bool:
        return self.permission is None or has_perm(user, self.permission)

    def fields_for(self, user) -> dict[str, FieldSpec]:
        """The fields this viewer may search and filter by, by key."""
        return {spec.key: spec for spec in self.fields if spec.usable_by(user)}


_MODULES: dict[str, SearchModule] = {}


def register(module: SearchModule) -> SearchModule:
    if module.key in _MODULES:
        raise ValueError(f'Search module {module.key!r} is registered twice.')
    _MODULES[module.key] = module
    return module


def all_modules() -> dict[str, SearchModule]:
    from apps.global_search import modules  # noqa: F401  (importing registers every module)
    return dict(_MODULES)


def modules_for(user) -> dict[str, SearchModule]:
    """The modules this viewer may search at all, in display order."""
    return {key: module for key, module in all_modules().items() if module.is_open_to(user)}
