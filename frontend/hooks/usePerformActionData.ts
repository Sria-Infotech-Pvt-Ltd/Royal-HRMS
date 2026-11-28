"use client";

// What the "Perform an action" modal needs to know about the employee and the company: their current record and history,
// the positions in their unit, other units with vacant seats (Org assignment), managers in their branch and the separation
// types, each turned into the option lists the fields render.

import { useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";
import { API } from "@/lib/api/endpoints";
import { unitMoveOptions } from "@/lib/orgMove";
import type { Employee, FieldOption } from "@/app/dashboard/employees/_data";
import type {
  ActionHistoryRow, ActionType, EmployeeDetailSnapshot,
} from "@/app/dashboard/employees/_components/PerformActionFields/types";

interface SeparationTypeOption { value: string; label: string; reason_applicable: boolean; notice_period_applicable: boolean }
interface ManagerOption { id: string; employee_id: string; full_name: string }

const toOption = (option: { value: string; label: string }): FieldOption => ({ value: option.value, label: option.label });

export function usePerformActionData(employee: Employee, actionType: ActionType | "", moveUnitId: string) {
  const { data: detail } = useFetch<EmployeeDetailSnapshot>(API.employees.detail(employee.code));
  const { data: history } = useFetch<ActionHistoryRow[]>(API.employees.actionHistory(employee.code));
  const { units, positions, positionsForUnit } = useOrgUnitsAndPositions();
  const { data: managers } = useFetch<ManagerOption[]>(
    employee.location ? `${API.employees.managerList}?branch=${encodeURIComponent(employee.location)}` : null,
  );
  const { data: separationTypes } = useFetch<SeparationTypeOption[]>(actionType === "separation" ? API.separation.types : null);

  const detailOrgUnitId = detail?.org_unit_id ?? "";
  const positionOptions = useMemo<FieldOption[]>(
    () => (detailOrgUnitId ? positionsForUnit(detailOrgUnitId, false).map(position => ({ value: position.id, label: position.title })) : []),
    [detailOrgUnitId, positionsForUnit],
  );
  // Org assignment: another unit and one of its VACANT positions (the server refuses a seat someone else holds).
  const moveUnitOptions = useMemo(() => unitMoveOptions(units, positions, detailOrgUnitId), [units, positions, detailOrgUnitId]);
  const movePositionOptions = useMemo<FieldOption[]>(
    () => (moveUnitId
      ? positions.filter(p => p.org_unit === moveUnitId && p.is_active && !p.holder).map(p => ({ value: p.id, label: p.grade ? `${p.title} · ${p.grade}` : p.title }))
      : []),
    [moveUnitId, positions],
  );
  const managerOptions = useMemo<FieldOption[]>(
    () => (managers ?? []).filter(manager => manager.id !== detail?.uuid).map(manager => ({ value: manager.id, label: manager.full_name })),
    [managers, detail?.uuid],
  );
  const separationTypeOptions = useMemo<FieldOption[]>(() => (separationTypes ?? []).map(toOption), [separationTypes]);

  return {
    detail, currentRecord: history?.find(row => row.is_current) ?? null, hasUnits: units.length > 0,
    positionOptions, moveUnitOptions, movePositionOptions, managerOptions, separationTypeOptions,
  };
}
