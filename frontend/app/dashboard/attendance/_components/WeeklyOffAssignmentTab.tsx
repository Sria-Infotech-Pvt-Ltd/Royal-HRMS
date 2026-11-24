"use client";

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { usePermission } from "@/hooks/usePermission";
import { useDepartmentOptions } from "@/hooks/useDepartmentOptions";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import { useToast } from "@/components/ToastProvider";
import BranchFilterSelect from "@/components/BranchFilterSelect";
import Modal from "@/components/Modal";
import ConfirmModal from "@/components/ConfirmModal";
import DateInput from "@/components/shared/DateInput";
import { MONO, Notice, Pager, Pill, SectionCard, TableStates, PersonCell } from "./SectionCard";
import { PALETTE } from "./attendancePalette";
import { localISODate } from "./monthView";

interface BranchOption { id: number; branch_name: string }

interface WeeklyOffPattern {
  id: string;
  name: string;
  policy_code: string;
}
interface PatternPage { results: WeeklyOffPattern[] }

interface AssignmentRow {
  employee_id: string;
  employee_name: string;
  department: string;
  branch: string;
  pattern_id: string | null;
  pattern_name: string | null;
  effective_from: string | null;
  effective_to: string | null;
  status: "Assigned" | "Not Assigned";
}
interface PaginatedAssignments {
  count: number; page: number; page_size: number; total_pages: number;
  results: AssignmentRow[];
}

const STATUS_OPTIONS = [
  { value: "",             label: "All" },
  { value: "assigned",     label: "Assigned" },
  { value: "unassigned",   label: "Not Assigned" },
];

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export default function WeeklyOffAssignmentTab() {
  const { showToast } = useToast();
  const t = useT();
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);
  const canAssign        = usePermission("attendance.create");

  const [branchInput, setBranchInput] = useState("");
  const [department, setDepartment]   = useState("");
  const [pattern, setPattern]         = useState("");
  const [status, setStatus]           = useState("");
  const [page, setPage]               = useState(1);

  const [assignTarget, setAssignTarget] = useState<AssignmentRow | null>(null);
  const [assignPattern, setAssignPattern] = useState("");
  const [assignDate, setAssignDate] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [assignErr, setAssignErr] = useState<string | null>(null);

  const [showBulk, setShowBulk] = useState(false);
  const [bulkPattern, setBulkPattern] = useState("");
  const [bulkDate, setBulkDate] = useState("");
  const [bulkBranch, setBulkBranch] = useState("");
  const [bulkDept, setBulkDept] = useState("");
  const [bulking, setBulking] = useState(false);
  const [bulkErr, setBulkErr] = useState<string | null>(null);
  const [confirmBulk, setConfirmBulk] = useState(false);

  const branch = unrestricted ? branchInput : effectiveBranch;

  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(
    unrestricted ? `${API.branches.list}?page_size=100` : null
  );
  const branches    = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);
  const departments = useDepartmentOptions(unrestricted, effectiveBranch);

  const { data: patternData } = useFetch<PatternPage>(`${API.attendance.weeklyDayPolicies}?page_size=50&is_active=true`);
  const patterns = patternData?.results ?? [];

  const listUrl = user
    ? `${API.attendance.weeklyOffAssignments}${toQuery({ branch, department, pattern, status, page, page_size: 20 })}`
    : null;
  const { data, loading, error, refetch } = useFetch<PaginatedAssignments>(listUrl);
  const rows = data?.results ?? [];

  function openAssign(row: AssignmentRow) {
    setAssignTarget(row);
    setAssignPattern(row.pattern_id ?? "");
    setAssignDate(localISODate());
    setAssignErr(null);
  }

  async function handleAssign() {
    if (!assignTarget) return;
    setAssigning(true);
    setAssignErr(null);
    try {
      await clientApi.post(API.attendance.weeklyOffAssignments, {
        employee_id: assignTarget.employee_id,
        pattern: assignPattern,
        effective_from: assignDate,
      });
      showToast(t("Weekly off pattern assigned to {name}.", { name: assignTarget.employee_name }), "success");
      setAssignTarget(null);
      refetch();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setAssignErr(e.message ?? t("Failed to assign pattern."));
    } finally {
      setAssigning(false);
    }
  }

  async function handleBulkAssign() {
    setConfirmBulk(false);
    setBulking(true);
    setBulkErr(null);
    try {
      const res = await clientApi.post<{ data: { count: number } }>(API.attendance.weeklyOffAssignmentsBulk, {
        pattern: bulkPattern,
        effective_from: bulkDate,
        branch: bulkBranch,
        department: bulkDept,
      });
      const count = res.data?.data?.count ?? 0;
      showToast(t("Weekly off pattern assigned to {count} employee(s).", { count }), "success");
      setShowBulk(false);
      refetch();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setBulkErr(e.message ?? t("Bulk assignment failed."));
    } finally {
      setBulking(false);
    }
  }

  const filters = (
    <>
      <BranchFilterSelect branches={branches} value={branchInput} onChange={value => { setBranchInput(value); setPage(1); }} locked={!unrestricted} lockedBranchName={effectiveBranch} />
      <select className="field-input field-select" style={{ width: 180 }} value={department} onChange={e => { setDepartment(e.target.value); setPage(1); }}>
        <option value="">{t("All Org Units")}</option>
        {departments.map(d => <option key={d} value={d}>{d}</option>)}
      </select>
      <select className="field-input field-select" style={{ width: 180 }} value={pattern} onChange={e => { setPattern(e.target.value); setPage(1); }}>
        <option value="">{t("All Patterns")}</option>
        {patterns.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <select className="field-input field-select" style={{ width: 150 }} value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
        {STATUS_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{t(opt.label)}</option>)}
      </select>
    </>
  );
  const bulkButton = canAssign && (
    <button className="btn btn-filled btn-sm" onClick={() => { setShowBulk(true); setBulkErr(null); setBulkDate(localISODate()); }} suppressHydrationWarning>
      <i className="ti ti-users" /> {t("Bulk Assign")}
    </button>
  );

  return (
    <>
      <SectionCard icon="ti-moon" colour={PALETTE.on_leave} title={t("Weekly Off Assignment")} count={data?.count ?? null} filters={filters} action={bulkButton} subtitle={t("Which weekly off pattern each employee follows. A new pattern applies from its effective date forward.")}>
        {error && <Notice tone="error" icon="ti-alert-circle">{error}</Notice>}
        <div className="table-wrap" style={{ marginTop: error ? 14 : 0 }}>
          <table>
            <thead>
              <tr><th>{t("Employee")}</th><th>{t("Department")}</th><th>{t("Weekly Off Pattern")}</th><th>{t("Effective From")}</th><th>{t("Effective To")}</th><th>{t("Status")}</th><th>{t("Actions")}</th></tr>
            </thead>
            <tbody>
              <TableStates columns={7} loading={loading} empty={rows.length === 0} icon="ti-users-off" title={t("No employees found.")} hint={t("Try clearing a filter above.")} />
              {rows.map(r => (
                <tr key={r.employee_id}>
                  <td><PersonCell name={r.employee_name} employeeId={r.employee_id} /></td>
                  <td>
                    <div style={{ fontSize: 13 }}>{r.department}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.branch}</div>
                  </td>
                  <td>{r.pattern_name ? <Pill colour={PALETTE.on_leave}>{r.pattern_name}</Pill> : "—"}</td>
                  <td style={MONO}>{r.effective_from ?? "—"}</td>
                  <td style={MONO}>{r.effective_to ?? "-"}</td>
                  <td><Pill colour={r.status === "Assigned" ? PALETTE.present : PALETTE.not_marked}>{t(r.status)}</Pill></td>
                  <td>
                    {canAssign && (
                      <button className="btn btn-outline btn-sm" style={{ padding: "3px 10px", fontSize: 11, color: PALETTE.brand }} onClick={() => openAssign(r)}>
                        <i className="ti ti-edit" /> {r.status === "Assigned" ? t("Change") : t("Assign")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pager data={data} page={page} onPage={setPage} noun={t("employees")} />
      </SectionCard>

      {/* ── Single assign modal ──────────────────────────────────────────── */}
      {assignTarget && (
        <Modal
          title={<><i className="ti ti-calendar-cog" /> {t("Assign Weekly Off Pattern")}</>}
          onClose={() => setAssignTarget(null)}
          closeDisabled={assigning}
          maxWidth="min(440px, 94vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setAssignTarget(null)} disabled={assigning} suppressHydrationWarning>{t("Cancel")}</button>
              <button className="btn btn-filled" onClick={handleAssign} disabled={assigning || !assignPattern || !assignDate} suppressHydrationWarning>
                {assigning ? t("Assigning…") : t("Assign")}
              </button>
            </>
          }
        >
          {assignErr && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {assignErr}</div>}
          <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 12 }}>
            {assignTarget.employee_name} ({assignTarget.employee_id})
            {assignTarget.status === "Assigned" && (
              <> — {t("currently")} <strong>{assignTarget.pattern_name}</strong>, {t("effective {date}", { date: assignTarget.effective_from ?? "" })}</>
            )}
          </p>
          <div className="field-group">
            <label className="field-label">{t("Weekly Off Pattern")}</label>
            <select className="field-input field-select" value={assignPattern} onChange={e => setAssignPattern(e.target.value)}>
              <option value="">{t("Select pattern…")}</option>
              {patterns.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">{t("Effective From")}</label>
            <DateInput className="field-input" value={assignDate} onChange={isoDate => setAssignDate(isoDate)} />
          </div>
          <p style={{ fontSize: 11, color: "var(--on-variant)" }}>
            {t("Past attendance is never affected — this pattern applies from the effective date forward only.")}
          </p>
        </Modal>
      )}

      {/* ── Bulk assign modal ────────────────────────────────────────────── */}
      {showBulk && (
        <Modal
          title={<><i className="ti ti-users" /> {t("Bulk Assign Weekly Off Pattern")}</>}
          onClose={() => setShowBulk(false)}
          closeDisabled={bulking}
          maxWidth="min(480px, 94vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowBulk(false)} disabled={bulking} suppressHydrationWarning>{t("Cancel")}</button>
              <button
                className="btn btn-filled"
                onClick={() => setConfirmBulk(true)}
                disabled={bulking || !bulkPattern || !bulkDate || (!bulkBranch && !bulkDept && unrestricted)}
                suppressHydrationWarning
              >
                {bulking ? t("Assigning…") : t("Assign to Matching Employees")}
              </button>
            </>
          }
        >
          {bulkErr && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {bulkErr}</div>}
          <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 12 }}>
            {t("Applies to every active employee matching the filters below — resolved on the server, so no employee list needs to load into the browser first.")}
          </p>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">{t("Company Code")}</label>
              <BranchFilterSelect
                branches={branches}
                value={unrestricted ? bulkBranch : effectiveBranch}
                onChange={v => setBulkBranch(v)}
                locked={!unrestricted}
                lockedBranchName={effectiveBranch}
              />
            </div>
            <div className="field-group">
              <label className="field-label">{t("Department")}</label>
              <select className="field-input field-select" value={bulkDept} onChange={e => setBulkDept(e.target.value)}>
                <option value="">{t("All Org Units")}</option>
                {departments.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          </div>
          <div className="field-group">
            <label className="field-label">{t("Weekly Off Pattern")}</label>
            <select className="field-input field-select" value={bulkPattern} onChange={e => setBulkPattern(e.target.value)}>
              <option value="">{t("Select pattern…")}</option>
              {patterns.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">{t("Effective From")}</label>
            <DateInput className="field-input" value={bulkDate} onChange={isoDate => setBulkDate(isoDate)} />
          </div>
        </Modal>
      )}

      {confirmBulk && (() => {
        const scopeBranch = unrestricted ? (bulkBranch || null) : effectiveBranch;
        const scopeParts = [
          scopeBranch ? t("Company Code {name}", { name: branches.find(b => String(b.id) === bulkBranch)?.branch_name ?? scopeBranch }) : null,
          bulkDept ? t("Department {name}", { name: bulkDept }) : null,
        ].filter(Boolean);
        const scopeText = scopeParts.length > 0 ? scopeParts.join(", ") : t("every active employee (no branch/department filter)");
        const patternName = patterns.find(p => p.id === bulkPattern)?.name ?? t("the selected pattern");
        return (
          <ConfirmModal
            title={t("Bulk-assign weekly off pattern?")}
            body={t("This assigns \"{pattern}\" effective {date} to every active employee matching: {scope}. The exact number of employees affected is resolved on the server and isn't known until this runs.", { pattern: patternName, date: bulkDate, scope: scopeText })}
            confirmLabel={t("Assign to Matching Employees")}
            saving={bulking}
            onConfirm={handleBulkAssign}
            onCancel={() => setConfirmBulk(false)}
          />
        );
      })()}
    </>
  );
}
