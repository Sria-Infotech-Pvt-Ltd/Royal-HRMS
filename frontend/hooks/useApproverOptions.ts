"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { ApproverOption, ApproverOptionsPage, ApproverRole, ApprovalRuleSummary } from "@/types/approvers";

const EMPTY_RULE: ApprovalRuleSummary = { l1: "", l2: "", l1_kind: "", l2_kind: "" };

/** The people the server will accept for `role` (and for `employeeId`, when the employee already exists), plus the approval rule. */
export function useApproverOptions(role: ApproverRole, employeeId?: string) {
  const params = new URLSearchParams({ kind: role, page_size: "100" });
  if (employeeId) params.set("employee_id", employeeId);
  const { data, loading, error } = useFetch<ApproverOptionsPage>(`${API.employees.approverOptions}?${params.toString()}`);
  const options: ApproverOption[] = data?.results ?? [];
  return { options, rule: data?.rule ?? EMPTY_RULE, loading, error };
}
