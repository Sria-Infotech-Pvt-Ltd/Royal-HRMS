# Open questions for the owner

New file, started in Phase 4 per its Section 3 Task C.5 instruction:
*"Where a view's current behaviour cannot be expressed exactly by the
engine, stop and record it in OPEN_QUESTIONS.md instead of
approximating."* Append to this file in later phases rather than
replacing it.

## Phase 4

1. **Which legacy ad-hoc scope patterns need their own scope type?**
   Phase 4's data-scope engine declares `direct_reports`, `all_reports`,
   `org_unit`, `branch`, `employee_group`, etc. on `RoleAssignment`, but
   only `own`/`all`/`legal_entity`/`my_legal_entity` have a working
   mapping (for the Phase 2 `CustomRecord` entity only — no core entity
   is mapped at all). Before Task C.5's "replace every ad hoc scope
   pattern" can proceed, each of the ~87 `can_manage_team`/
   `can_manage_branch` usages and the department/org-unit-chain helpers
   in `apps/accounts/services_approval.py` needs its own verified
   mapping — not attempted in this phase.
2. **`EmployeeBranchAccess`'s real purpose vs. the prompt's assumption.**
   The prompt's Task C.1 names it as feeding `my_branches` data-access
   scope. Its actual, current, sole documented purpose (per its own
   model docstring) is punch-in geofencing validation — not general
   record-visibility scoping. Using it for `my_branches` access scope
   may be the RIGHT design decision, but it would be giving this table a
   SECOND meaning it doesn't have today, which needs an explicit
   decision, not an assumption.
3. **Reporting-tree source of truth for `all_reports`.** Task C.1 asks
   "match the code's actual behaviour; verify it" for whether
   `can_manage_team` means the reporting-manager chain, the org chart,
   or both. This phase did not trace that verification — flagged for
   whoever builds the Task I migration.
4. **`roles.manage` permission does not exist yet.** The seeded
   (inactive) SoD suggestion `manage_roles_vs_approve_own_access`
   references a `roles.manage` codename that isn't in the current
   Permission table — it's a placeholder for the owner to create (or
   rename to an existing equivalent) when activating that rule.
5. **Which 20 `is_superuser`/`is_staff` usages are genuinely break-glass
   vs. convenience shortcuts?** Task D.3 asks to "keep only those needed
   for Django admin and break-glass" — the exact list (14 citations,
   gathered this phase) was catalogued in `PHASE4_REPORT.md` but not
   individually triaged/removed; that triage is itself a judgment call
   for the owner on each one, not something to guess at silently.
