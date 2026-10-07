"""
Phase 4 Task G — module toggle enforcement. Reuses Phase 1's existing
`services_flags.is_module_enabled(module, legal_entity)` (already built,
never enforced anywhere) — this module adds the actual enforcement
PRIMITIVE, chosen explicitly: **403, not 404** (Task G's "choose one and
document it" — 403 tells an authorized-but-toggled-off user WHY, a 404
would be indistinguishable from a real missing resource and makes
debugging a toggle mistake harder for the admin who flipped it).

NOT wired into any existing endpoint's menu metadata, scheduled jobs, or
notification firing in this pass — see PHASE4_REPORT.md.
"""
from __future__ import annotations

from apps.platform_core import services_flags


class ModuleDisabledError(Exception):
    def __init__(self, module: str):
        self.module = module
        self.message = f'The "{module}" module is disabled for this legal entity.'
        super().__init__(self.message)


def require_module_enabled(module: str, legal_entity) -> None:
    if not services_flags.is_module_enabled(module, legal_entity):
        raise ModuleDisabledError(module)
