"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

interface DepartmentOption { id: number; name: string }
interface EmployeeLite { department: string }

// Unrestricted users (system_admin) see the full company-wide department list.
// Scoped users (hr_admin) must only see departments that actually have
// employees in their branch — the global /departments/ list isn't branch-aware,
// so we derive options from the branch's own employee roster instead.
export function useDepartmentOptions(isUnrestricted: boolean, effectiveBranch: string): string[] {
  const { data: globalData } = useFetch<DepartmentOption[] | { results: DepartmentOption[] }>(
    isUnrestricted ? API.departments.list : null
  );
  const { data: employeeData } = useFetch<{ results: EmployeeLite[] }>(
    !isUnrestricted && effectiveBranch
      ? `${API.employees.list}?branch=${encodeURIComponent(effectiveBranch)}&page_size=200`
      : null
  );

  if (isUnrestricted) {
    const list = Array.isArray(globalData) ? globalData : (globalData?.results ?? []);
    return list.map(d => d.name);
  }

  const names = new Set(
    (employeeData?.results ?? [])
      .map(e => e.department)
      .filter((name): name is string => Boolean(name))
  );
  return Array.from(names).sort();
}
