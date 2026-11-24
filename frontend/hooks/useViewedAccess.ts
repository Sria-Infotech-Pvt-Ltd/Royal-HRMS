"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { isViewAsTarget } from "@/lib/viewAs";

export interface ViewedAccess {
  permissions: string[];
  can_manage_team: boolean;
  can_manage_branch: boolean;
  is_superuser: boolean;
}

/**
 * While someone looks at an employee's workspace ("View as employee"), what that EMPLOYEE may open. The login session still
 * describes the person looking, so the top bar and the search box would otherwise offer the viewer's pages (Document Center,
 * Payroll ...) on a screen that is meant to show only what the employee has. `access` stays null until it has loaded.
 */
export function useViewedAccess(): { isViewing: boolean; access: ViewedAccess | null } {
  const pathname = usePathname();
  const target = useSearchParams().get("as");
  const viewed = pathname.startsWith("/dashboard/ess") && isViewAsTarget(target) ? target : null;
  // The employee is part of the address, so looking at another employee is a new request rather than the previous answer.
  const { data } = useFetch<ViewedAccess>(viewed ? `${API.employees.myAccess}?as=${encodeURIComponent(viewed)}` : null);
  return { isViewing: viewed !== null, access: viewed ? data : null };
}
