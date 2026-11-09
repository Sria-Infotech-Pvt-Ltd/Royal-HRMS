"use client";

import { useApproverOptions } from "@/hooks/useApproverOptions";

/** The three dropdowns' options in one place. Each list is exactly what the server accepts for that role. */
export function useApproverChoices(employeeId?: string) {
  const managers = useApproverOptions("reporting_manager", employeeId);
  const l1 = useApproverOptions("l1", employeeId);
  const l2 = useApproverOptions("l2", employeeId);
  return {
    managers: managers.options,
    l1: l1.options,
    l2: l2.options,
    rule: l1.rule,
    loading: managers.loading || l1.loading || l2.loading,
    failed: Boolean(managers.error || l1.error || l2.error),
  };
}
