"use client";

// The OT Entry tab: add an overtime entry, and see the records. The form and the records are the OtEntryForm and OtRecordsCard beside this
// file; this one loads the data, checks the form and sends it.

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import { useToast } from "@/components/ToastProvider";
import BranchFilterSelect from "@/components/BranchFilterSelect";
import type { OvertimeCreatePayload, PaginatedOvertime } from "@/types/attendance";
import OtEntryForm, { type PickerEmployee } from "./OtEntryForm";
import OtRecordsCard from "./OtRecordsCard";
import { validateOtForm } from "./otEntry";
import { localISODate } from "./monthView";

interface BranchOption { id: number; branch_name: string }

/** A fresh form for the viewer's own today (not the UTC date, and not the date the page was first loaded). */
const emptyForm = (date: string): OvertimeCreatePayload => ({ employee_id: "", date, ot_type: "regular", ot_start: "18:00", ot_end: "20:00", approved_by: "", reason: "" });

export default function OtEntryTab() {
  const { showToast } = useToast();
  const t = useT();
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const canCreate       = usePermission("attendance.create");
  const effectiveBranch = getEffectiveBranch(user);

  const [todayISO]                  = useState(() => localISODate());
  const [form, setForm]             = useState<OvertimeCreatePayload>(() => emptyForm(todayISO));
  const [branchInput, setBranchInput] = useState("");
  const [page, setPage]             = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError]   = useState<string | null>(null);

  const branch = unrestricted ? branchInput : effectiveBranch;

  // Everyone, up to 500, so the picker's search covers the whole company rather than the first 200.
  const { data: employeeData } = useFetch<{ results: PickerEmployee[] }>(`${API.employees.list}?page_size=500`);
  const approverUrl = branch ? `${API.employees.hrList}?branch=${encodeURIComponent(branch)}` : null;
  const { data: approvers } = useFetch<PickerEmployee[]>(approverUrl);
  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(unrestricted ? `${API.branches.list}?page_size=100` : null);
  const branches = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);

  const otUrl = user ? `${API.attendance.overtime}?${branch ? `branch=${encodeURIComponent(branch)}&` : ""}page=${page}&page_size=20` : null;
  const { data: otData, loading, error, refetch } = useFetch<PaginatedOvertime>(otUrl);

  function setField<K extends keyof OvertimeCreatePayload>(key: K, value: OvertimeCreatePayload[K]) {
    setForm(previous => ({ ...previous, [key]: value }));
    setFormError(null);
  }

  async function handleSubmit() {
    const problem = validateOtForm(form);
    if (problem) { setFormError(problem); return; }
    setSubmitting(true);
    setFormError(null);
    try {
      await clientApi.post(API.attendance.overtimeCreate, form);
      showToast(t("Overtime entry created."), "success");
      setForm({ ...emptyForm(todayISO), date: form.date });   // ready for the next entry on the same day
      refetch();
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? t("Failed to create overtime entry.");
      setFormError(message);
      showToast(message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <OtEntryForm
        form={form} onField={setField} employees={employeeData?.results ?? []} approvers={approvers ?? []} todayISO={todayISO}
        error={formError} canCreate={canCreate} submitting={submitting} onSubmit={handleSubmit}
        onReset={() => { setForm(emptyForm(todayISO)); setFormError(null); }}
      />
      <OtRecordsCard
        rows={otData?.results ?? []} data={otData ?? null} loading={loading} error={error} page={page} onPage={setPage}
        filter={<BranchFilterSelect branches={branches} value={branchInput} onChange={value => { setBranchInput(value); setPage(1); }} locked={!unrestricted} lockedBranchName={effectiveBranch} width={160} />}
      />
    </div>
  );
}
