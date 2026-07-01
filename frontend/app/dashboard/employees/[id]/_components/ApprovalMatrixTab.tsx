"use client";

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { getStoredUser } from "@/lib/auth";
import clientApi from "@/lib/clientApi";
import type { WorkflowMatrixRow, ApprovalWorkflowType } from "@/types/approvalMatrix";

interface PickerEmployee {
  id:          string;
  full_name:   string;
  employee_id: string;
  department:  string;
  branch:      string;
}

// ─── Override Editor Modal ────────────────────────────────────────────────────

interface OverrideEditorProps {
  row:          WorkflowMatrixRow;
  employeeCode: string;
  branch:       string;
  onSaved:      (updated: WorkflowMatrixRow) => void;
  onClose:      () => void;
}

function OverrideEditor({ row, employeeCode, branch, onSaved, onClose }: OverrideEditorProps) {
  const [l1Id,    setL1Id]    = useState<string>(row.l1_is_override ? (row.l1_approver_id ?? "") : "");
  const [l2Id,    setL2Id]    = useState<string>(row.l2_is_override ? (row.l2_approver_id ?? "") : "");
  const [saving,  setSaving]  = useState(false);
  const [apiError, setApiError] = useState("");

  const branchParam = branch ? `?branch=${encodeURIComponent(branch)}` : "";

  const { data: managersRaw, loading: loadingManagers } =
    useFetch<PickerEmployee[]>(`${API.employees.managerList}${branchParam}`);
  const { data: hrsRaw, loading: loadingHrs } =
    useFetch<PickerEmployee[]>(`${API.employees.hrList}${branchParam}`);

  const managers = managersRaw ?? [];
  const hrs      = hrsRaw      ?? [];

  async function handleSave() {
    setSaving(true);
    setApiError("");
    try {
      const body: {
        workflow_type:  ApprovalWorkflowType;
        l1_override_id: string | null;
        l2_override_id: string | null;
      } = {
        workflow_type:  row.workflow_type,
        l1_override_id: l1Id || null,
        l2_override_id: l2Id || null,
      };
      const res = await clientApi.patch<{ data: WorkflowMatrixRow }>(
        API.employees.approvalMatrix(employeeCode),
        body,
      );
      onSaved(res.data.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiError(msg || "Failed to save override.");
    } finally {
      setSaving(false);
    }
  }

  const SELECT_CLS =
    "w-full px-3.5 py-[7px] rounded-md border text-[13px] outline-none transition-all bg-white appearance-none cursor-pointer" +
    " focus:border-[var(--primary)] focus:ring-2 focus:ring-[rgba(30,78,140,0.10)]";
  const CHEVRON = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>")`;

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <div className="modal-title">Override Approvers — {row.workflow_label}</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body">
          {apiError && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" /> {apiError}
            </div>
          )}
          <div className="alert alert-warn mb-16" style={{ fontSize: 13 }}>
            <i className="ti ti-info-circle" />
            <div>
              Select a specific person to override, or leave as <strong>— Global default —</strong> to revert.
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* L1 — Managers */}
            <div className="field-group">
              <label className="field-label">
                L1 Approver
                <span style={{ fontWeight: 400, color: "var(--on-variant)", marginLeft: 4 }}>
                  (default: {row.l1_approver_label})
                </span>
              </label>
              <select
                value={l1Id}
                onChange={e => setL1Id(e.target.value)}
                disabled={loadingManagers}
                className={SELECT_CLS}
                style={{
                  borderColor: "#d3dae8",
                  backgroundImage: CHEVRON,
                  backgroundRepeat: "no-repeat",
                  backgroundPosition: "right 10px center",
                  backgroundSize: "15px",
                  paddingRight: "2.5rem",
                }}
              >
                <option value="">
                  {loadingManagers ? "Loading…" : "— Global default —"}
                </option>
                {managers.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.full_name} ({m.employee_id})
                  </option>
                ))}
              </select>
            </div>

            {/* L2 — HRs (only if row has L2) */}
            {row.l2_approver_role && (
              <div className="field-group">
                <label className="field-label">
                  L2 Approver
                  <span style={{ fontWeight: 400, color: "var(--on-variant)", marginLeft: 4 }}>
                    (default: {row.l2_approver_label})
                  </span>
                </label>
                <select
                  value={l2Id}
                  onChange={e => setL2Id(e.target.value)}
                  disabled={loadingHrs}
                  className={SELECT_CLS}
                  style={{
                    borderColor: "#d3dae8",
                    backgroundImage: CHEVRON,
                    backgroundRepeat: "no-repeat",
                    backgroundPosition: "right 10px center",
                    backgroundSize: "15px",
                    paddingRight: "2.5rem",
                  }}
                >
                  <option value="">
                    {loadingHrs ? "Loading…" : "— Global default —"}
                  </option>
                  {hrs.map(h => (
                    <option key={h.id} value={h.id}>
                      {h.full_name} ({h.employee_id})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save Override"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Approver Cell ────────────────────────────────────────────────────────────

function ApproverCell({ name, label, isOverride }: {
  name:       string | null;
  label:      string;
  isOverride: boolean;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>
        {name || label}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
        {isOverride ? (
          <span style={{
            fontSize: 10, fontWeight: 600, padding: "1px 7px", borderRadius: 20,
            background: "rgba(30,78,140,0.10)", color: "var(--primary)",
            textTransform: "uppercase", letterSpacing: "0.04em",
          }}>
            Override
          </span>
        ) : (
          <span style={{ fontSize: 11, color: "var(--outline)" }}>
            Global default
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────

interface Props {
  employeeCode: string;
  branch:       string;
}

export function ApprovalMatrixTab({ employeeCode, branch }: Props) {
  const { data, loading, error, refetch } = useFetch<WorkflowMatrixRow[]>(
    API.employees.approvalMatrix(employeeCode),
  );
  const [editing, setEditing] = useState<WorkflowMatrixRow | null>(null);

  const currentUser = getStoredUser();
  const canEdit = currentUser?.role === "hr_admin" || currentUser?.role === "system_admin";

  function handleSaved(_updated: WorkflowMatrixRow) {
    refetch();
    setEditing(null);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 gap-2 text-[13px] text-[var(--on-variant)]">
        <i className="ti ti-loader-2 animate-spin text-[20px]" style={{ color: "var(--primary)" }} />
        Loading approval matrix…
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-error">
        <i className="ti ti-alert-circle" /> {error}
      </div>
    );
  }

  const rows = (data ?? []).filter(r => (r.workflow_type as string) !== "loan");

  return (
    <div className="settings-card">
      <div style={{ marginBottom: 16 }}>
        <div className="settings-card-title" style={{ marginBottom: 2 }}>Approval Matrix</div>
        <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
          Specific person overrides take precedence over global role defaults.
        </div>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid var(--outline-v)" }}>
              <th style={{ textAlign: "left", padding: "10px 12px", color: "var(--on-variant)", fontWeight: 600, width: "25%" }}>Workflow</th>
              <th style={{ textAlign: "left", padding: "10px 12px", color: "var(--on-variant)", fontWeight: 600 }}>L1 Approver</th>
              <th style={{ textAlign: "left", padding: "10px 12px", color: "var(--on-variant)", fontWeight: 600 }}>L2 Approver</th>
              {canEdit && <th style={{ width: 90 }} />}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={canEdit ? 4 : 3} style={{ padding: "40px 12px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                  No approval matrix configured.
                </td>
              </tr>
            ) : rows.map(row => (
              <tr key={row.workflow_type} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                <td style={{ padding: "14px 12px", fontWeight: 500, color: "var(--on-bg)" }}>
                  {row.workflow_label}
                </td>
                <td style={{ padding: "14px 12px" }}>
                  <ApproverCell
                    name={row.l1_approver_name}
                    label={row.l1_approver_label}
                    isOverride={row.l1_is_override}
                  />
                </td>
                <td style={{ padding: "14px 12px" }}>
                  {row.l2_approver_role ? (
                    <ApproverCell
                      name={row.l2_approver_name}
                      label={row.l2_approver_label}
                      isOverride={row.l2_is_override}
                    />
                  ) : (
                    <span style={{ fontSize: 13, color: "var(--outline)", opacity: 0.6 }}>Single level</span>
                  )}
                </td>
                {canEdit && (
                  <td style={{ padding: "14px 12px", textAlign: "right" }}>
                    <button
                      className="btn btn-ghost"
                      style={{ padding: "4px 10px", fontSize: 12 }}
                      onClick={() => setEditing(row)}
                    >
                      <i className="ti ti-edit" /> Override
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <OverrideEditor
          row={editing}
          employeeCode={employeeCode}
          branch={branch}
          onSaved={handleSaved}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
