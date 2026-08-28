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
  positionsForUnit:   (orgUnitId: string, vacantOnly?: boolean) => Position[];
}

// Shared source of Org Unit / Position option lists for every Position
// picker across the app (Create Employee, Onboarding Approval, Employee
// Edit's "Reassign Position") — same endpoints/page_size OrgStructureClient
// itself already uses, so this reuses whatever the API already returns
// rather than adding a new query shape.
export function useOrgUnitsAndPositions(): Result {
  const { data: unitData, loading: unitsLoading } =
    useFetch<OrgUnit[] | { results: OrgUnit[] }>(`${API.orgStructure.units.list}?page_size=200`);
  const { data: posData, loading: positionsLoading } =
    useFetch<Position[] | { results: Position[] }>(`${API.orgStructure.positions.list}?page_size=200`);

  const units     = useMemo(() => (Array.isArray(unitData) ? unitData : (unitData?.results ?? [])), [unitData]);
  const positions = useMemo(() => (Array.isArray(posData)  ? posData  : (posData?.results ?? [])), [posData]);

  function positionsForUnit(orgUnitId: string, vacantOnly = false): Position[] {
    return positions.filter(p => p.org_unit === orgUnitId && p.is_active && (!vacantOnly || !p.holder));
  }

  return { units, positions, loading: unitsLoading || positionsLoading, positionsForUnit };
}
