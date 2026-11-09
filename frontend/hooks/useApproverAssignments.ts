"use client";

import { useCallback, useState } from "react";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { parseApiError } from "@/lib/apiError";
import type { ApproverAssignments, ApproverSelection } from "@/types/approvers";

/** One employee's approver assignments for HR: what is assigned, who will actually approve, and a save that reports the server's per-field messages. */
export function useApproverAssignments(employeeCode: string) {
  const { data, loading, error, refetch } = useFetch<ApproverAssignments>(API.employees.approverAssignments(employeeCode));
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saveError, setSaveError] = useState<string | null>(null);

  const save = useCallback(async (selection: ApproverSelection): Promise<boolean> => {
    setSaving(true);
    setFieldErrors({});
    setSaveError(null);
    try {
      await clientApi.put(API.employees.approverAssignments(employeeCode), {
        reporting_manager_id: selection.reporting_manager_id || null,
        l1_approver_id: selection.l1_approver_id || null,
        hr_id: selection.hr_id || null,
      });
      refetch();
      return true;
    } catch (err: unknown) {
      const parsed = parseApiError(err, "Could not save the approvers.");
      setFieldErrors(parsed.fieldErrors);
      setSaveError(parsed.message);
      return false;
    } finally {
      setSaving(false);
    }
  }, [employeeCode, refetch]);

  return { assignments: data, loading, error, saving, fieldErrors, saveError, save };
}
