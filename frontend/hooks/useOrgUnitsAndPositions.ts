import { useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { OrgUnit, Position } from "@/types/orgStructure";

interface Result {
  units:              OrgUnit[];
  positions:          Position[];
  loading:            boolean;
  // Active positions under `orgUnitId`, optionally hiding ones that
  // already have a current holder — pass vacantOnly for a hiring flow
  // (Create Employee, Onboarding Approval) so a new hire can't
  // accidentally displace an existing employee. Left off for a
  // "Reassign Position" action, which intentionally allows it (same
  // pattern as the Org Chart's own AssignHolderModal).
  // branchId narrows further to positions tied to that one branch —
  // a position with branch === null sits in the shared company-wide tree
  // and matches every branch (same convention as OrgTree.tsx's own
  // matchesBranch()), so it's never excluded just because a branch filter
  // is set.
  positionsForUnit:   (orgUnitId: string, vacantOnly?: boolean, branchId?: number | null) => Position[];
  // Preview-only mirror of the backend's
  // services_approval.resolve_employee_department_name() — walks up from
  // `orgUnitId` via `parent` and returns the name of the nearest unit
  // marked is_department_level, or null if none in the chain is marked.
  // Purely cosmetic (what a picker shows before submitting); the backend
  // is the actual source of truth once a Position is assigned.
  resolveDepartmentName: (orgUnitId: string) => string | null;
}

// The most the org-structure list endpoints return in one page (max_page_size there). 200 cut off the positions of a real
// org chart (223 seats), so seats past the 200th never appeared in the position and vacancy pickers.
const ORG_LIST_PAGE_SIZE = 1000;

// Shared source of Org Unit / Position option lists for every Position
// picker across the app (Create Employee, Onboarding Approval, Employee
// Edit's "Reassign Position", Org assignment, Move employees) — the same
// endpoints OrgStructureClient uses, asking for every row in one page.
export function useOrgUnitsAndPositions(): Result {
  const { data: unitData, loading: unitsLoading } =
    useFetch<OrgUnit[] | { results: OrgUnit[] }>(`${API.orgStructure.units.list}?page_size=${ORG_LIST_PAGE_SIZE}`);
  const { data: posData, loading: positionsLoading } =
    useFetch<Position[] | { results: Position[] }>(`${API.orgStructure.positions.list}?page_size=${ORG_LIST_PAGE_SIZE}`);

  const units     = useMemo(() => (Array.isArray(unitData) ? unitData : (unitData?.results ?? [])), [unitData]);
  const positions = useMemo(() => (Array.isArray(posData)  ? posData  : (posData?.results ?? [])), [posData]);

  function positionsForUnit(orgUnitId: string, vacantOnly = false, branchId: number | null = null): Position[] {
    return positions.filter(p =>
      p.org_unit === orgUnitId && p.is_active
      && (!vacantOnly || !p.holder)
      && (branchId == null || p.branch === null || p.branch === branchId),
    );
  }

  function resolveDepartmentName(orgUnitId: string): string | null {
    const byId = new Map(units.map(u => [u.id, u]));
    let unit = byId.get(orgUnitId) ?? null;
    const seen = new Set<string>();
    while (unit && !seen.has(unit.id)) {
      if (unit.is_department_level) return unit.name;
      seen.add(unit.id);
      unit = unit.parent ? (byId.get(unit.parent) ?? null) : null;
    }
    return null;
  }

  return { units, positions, loading: unitsLoading || positionsLoading, positionsForUnit, resolveDepartmentName };
}
