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

const SELECT_CLS =
  "w-full px-3.5 py-[7px] rounded-md border text-[13px] outline-none transition-all bg-white appearance-none cursor-pointer" +
  " focus:border-[var(--primary)] focus:ring-2 focus:ring-[rgba(30,78,140,0.10)]";
const CHEVRON = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>")`;
const SELECT_STYLE = {
  borderColor: "#d3dae8",
  backgroundImage: CHEVRON,
  backgroundRepeat: "no-repeat" as const,
  backgroundPosition: "right 10px center" as const,
  backgroundSize: "15px",
  paddingRight: "2.5rem",
};

// ─── Relationship Editor Modal ────────────────────────────────────────────────

interface RelationshipEditorProps {
  title:        string;
  listEndpoint: string;
  currentId:    string;
  saveEndpoint: string;
  bodyKey:      string;
  onSaved:      (id: string, name: string, empId: string) => void;
  onClose:      () => void;
}

function RelationshipEditorModal({
  title, listEndpoint, currentId, saveEndpoint, bodyKey, onSaved, onClose,
}: RelationshipEditorProps) {
  const [selectedId, setSelectedId] = useState(currentId);
  const [saving,     setSaving]     = useState(false);
  const [apiError,   setApiError]   = useState("");

  const { data: listRaw, loading } = useFetch<PickerEmployee[]>(listEndpoint);
  const people = listRaw ?? [];

  async function handleSave() {
    if (!selectedId) return;
    setSaving(true);
    setApiError("");
    try {
      await clientApi.patch(saveEndpoint, { [bodyKey]: selectedId });
      const person = people.find(p => p.id === selectedId);
      onSaved(selectedId, person?.full_name ?? "", person?.employee_id ?? "");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiError(msg || "Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 440 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">{title}</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          {apiError && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" /> {apiError}
            </div>
          )}
          <div className="field-group">
            <label className="field-label">Select person</label>
            <select
              value={selectedId}
              onChange={e => setSelectedId(e.target.value)}
              disabled={loading}
              className={SELECT_CLS}
              style={SELECT_STYLE}
            >
              <option value="">{loading ? "Loading…" : "— Select —"}</option>
              {people.map(p => (
                <option key={p.id} value={p.id}>
                  {p.full_name} ({p.employee_id})
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-filled"
            onClick={handleSave}
            disabled={saving || !selectedId || loading}
          >
            {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Override Editor Modal ────────────────────────────────────────────────────

interface OverrideEditorProps {
  row:              WorkflowMatrixRow;
  employeeCode:     string;
  branch:           string;
  defaultManagerId: string;
  defaultHrId:      string;
  onSaved:          (updated: WorkflowMatrixRow) => void;
  onClose:          () => void;
}

function OverrideEditor({ row, employeeCode, branch, defaultManagerId, defaultHrId, onSaved, onClose }: OverrideEditorProps) {
  const [l1Id,     setL1Id]    = useState<string>(row.l1_is_override ? (row.l1_approver_id ?? "") : (defaultManagerId ?? ""));
  const [l2Id,     setL2Id]    = useState<string>(row.l2_is_override ? (row.l2_approver_id ?? "") : (defaultHrId ?? ""));
  const [saving,   setSaving]  = useState(false);
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
                style={SELECT_STYLE}
              >
                <option value="">{loadingManagers ? "Loading…" : "— Global default —"}</option>
                {managers.map(m => (
                  <option key={m.id} value={m.id}>{m.full_name} ({m.employee_id})</option>
                ))}
              </select>
            </div>

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
                  style={SELECT_STYLE}
                >
                  <option value="">{loadingHrs ? "Loading…" : "— Global default —"}</option>
                  {hrs.map(h => (
                    <option key={h.id} value={h.id}>{h.full_name} ({h.employee_id})</option>
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
  if (!name) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ fontSize: 13, color: "var(--outline)", fontStyle: "italic" }}>Not assigned</div>
        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Role: {label}</div>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{name}</div>
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
          <span style={{ fontSize: 11, color: "var(--outline)" }}>Global default</span>
        )}
      </div>
    </div>
  );
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────

interface Props {
  employeeCode:        string;
  branch:              string;
  defaultManagerId?:   string;
  defaultManagerName?: string;
  defaultHrId?:        string;
  defaultHrName?:      string;
  onManagerChanged?:   (id: string, name: string) => void;
  onHrChanged?:        (id: string, name: string) => void;
}

export function ApprovalMatrixTab({
  employeeCode,
  branch,
  defaultManagerId   = "",
  defaultManagerName = "",
  defaultHrId        = "",
  defaultHrName      = "",
  onManagerChanged,
  onHrChanged,
}: Props) {
  const { data, loading, error, refetch } = useFetch<WorkflowMatrixRow[]>(
    API.employees.approvalMatrix(employeeCode),
  );
  const [editing, setEditing] = useState<WorkflowMatrixRow | null>(null);

  // Local relationship state — keeps UI in sync without a full page refresh
  const [managerId,   setManagerId]   = useState(defaultManagerId);
  const [managerName, setManagerName] = useState(defaultManagerName);
  const [hrId,        setHrId]        = useState(defaultHrId);
  const [hrName,      setHrName]      = useState(defaultHrName);

  const [editingManager, setEditingManager] = useState(false);
  const [editingHr,      setEditingHr]      = useState(false);

  const currentUser = getStoredUser();
  const canEdit = currentUser?.role === "hr_admin" || currentUser?.role === "system_admin";

  function handleSaved(_updated: WorkflowMatrixRow) {
    refetch();
    setEditing(null);
  }

  const branchParam = branch ? `?branch=${encodeURIComponent(branch)}` : "";

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
    <>
      {/* ── Reporting Relationships card ── */}
      <div className="settings-card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div>
            <div className="settings-card-title" style={{ marginBottom: 2 }}>Reporting Relationships</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Reporting manager and branch HR assigned to this employee
            </div>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {/* Reporting Manager */}
          <div style={{
            padding: "14px 16px", borderRadius: 8,
            border: "1px solid var(--outline-v)", background: "var(--bg-low)",
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--on-variant)", marginBottom: 8 }}>
              <i className="ti ti-user-check" style={{ marginRight: 4, color: "var(--primary)" }} />
              Reporting Manager
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ flex: 1 }}>
                {managerName ? (
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{managerName}</div>
                ) : (
                  <div style={{ fontSize: 13, color: "var(--outline)", fontStyle: "italic" }}>Not assigned</div>
                )}
              </div>
              {canEdit && (
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ padding: "3px 8px", fontSize: 12, flexShrink: 0 }}
                  onClick={() => setEditingManager(true)}
                >
                  <i className="ti ti-edit" style={{ fontSize: 13 }} /> Edit
                </button>
              )}
            </div>
          </div>

          {/* Branch HR */}
          <div style={{
            padding: "14px 16px", borderRadius: 8,
            border: "1px solid var(--outline-v)", background: "var(--bg-low)",
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--on-variant)", marginBottom: 8 }}>
              <i className="ti ti-users" style={{ marginRight: 4, color: "var(--primary)" }} />
              Branch HR
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ flex: 1 }}>
                {hrName ? (
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{hrName}</div>
                ) : (
                  <div style={{ fontSize: 13, color: "var(--outline)", fontStyle: "italic" }}>Not assigned</div>
                )}
              </div>
              {canEdit && (
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ padding: "3px 8px", fontSize: 12, flexShrink: 0 }}
                  onClick={() => setEditingHr(true)}
                >
                  <i className="ti ti-edit" style={{ fontSize: 13 }} /> Edit
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Approval Matrix table ── */}
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
      </div>

      {/* ── Modals ── */}
      {editing && (
        <OverrideEditor
          row={editing}
          employeeCode={employeeCode}
          branch={branch}
          defaultManagerId={managerId}
          defaultHrId={hrId}
          onSaved={handleSaved}
          onClose={() => setEditing(null)}
        />
      )}

      {editingManager && (
        <RelationshipEditorModal
          title="Edit Reporting Manager"
          listEndpoint={`${API.employees.managerList}${branchParam}`}
          currentId={managerId}
          saveEndpoint={API.employees.reportingManager(employeeCode)}
          bodyKey="reporting_manager_id"
          onSaved={(id, name) => {
            setManagerId(id);
            setManagerName(name);
            setEditingManager(false);
            onManagerChanged?.(id, name);
          }}
          onClose={() => setEditingManager(false)}
        />
      )}

      {editingHr && (
        <RelationshipEditorModal
          title="Edit Branch HR"
          listEndpoint={`${API.employees.hrList}${branchParam}`}
          currentId={hrId}
          saveEndpoint={API.employees.hr(employeeCode)}
          bodyKey="hr_id"
          onSaved={(id, name) => {
            setHrId(id);
            setHrName(name);
            setEditingHr(false);
            onHrChanged?.(id, name);
          }}
          onClose={() => setEditingHr(false)}
        />
      )}
    </>
  );
}
