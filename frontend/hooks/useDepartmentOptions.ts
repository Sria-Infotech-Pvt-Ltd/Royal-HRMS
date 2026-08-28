"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { OrgUnit } from "@/types/orgStructure";

interface EmployeeLite { department: string }

// Unrestricted users (system_admin) see every OrgUnit marked as
// representing a real department (is_department_level) — Department
// itself is retired. Scoped users (hr_admin) must only see departments
// that actually have employees in their branch — that global list isn't
// branch-aware, so we derive options from the branch's own employee
// roster instead (User.department, kept in sync via Position).
export function useDepartmentOptions(isUnrestricted: boolean, effectiveBranch: string): string[] {
  const { data: globalData } = useFetch<OrgUnit[] | { results: OrgUnit[] }>(
    isUnrestricted ? `${API.orgStructure.units.list}?page_size=200` : null
  );
  const { data: employeeData } = useFetch<{ results: EmployeeLite[] }>(
    !isUnrestricted && effectiveBranch
      ? `${API.employees.list}?branch=${encodeURIComponent(effectiveBranch)}&page_size=200`
      : null
  );

  if (isUnrestricted) {
    const list = Array.isArray(globalData) ? globalData : (globalData?.results ?? []);
    return list.filter(u => u.is_department_level).map(u => u.name);
  }

  const names = new Set(
    (employeeData?.results ?? [])
      .map(e => e.department)
      .filter((name): name is string => Boolean(name))
  );
  return Array.from(names).sort();
}
