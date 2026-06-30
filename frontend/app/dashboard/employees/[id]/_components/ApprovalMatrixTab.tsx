"use client";

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { getStoredUser } from "@/lib/auth";
import clientApi from "@/lib/clientApi";
import type { WorkflowMatrixRow, ApprovalWorkflowType } from "@/types/approvalMatrix";

interface EmployeeResult {
  uuid:        string;
  full_name:   string;
  employee_id: string;
  department:  string;
}

interface ListResponse { results: EmployeeResult[]; }

// ─── Module-level component — must NOT be defined inside another component ───

interface SearchInputProps {
  label:      string;
  search:     string;
  onSearch:   (v: string) => void;
  selected:   EmployeeResult | null;
  onSelect:   (e: EmployeeResult) => void;
  onClear:    () => void;
  results:    EmployeeResult[];
  searching:  boolean;
}

function EmployeeSearchInput({
  label, search, onSearch, selected, onSelect, onClear, results, searching,
}: SearchInputProps) {
  return (
    <div className="field-group">
      <label className="field-label">{label}</label>
      {selected ? (
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          background: "var(--bg-mid)", borderRadius: 8, padding: "8px 12px",
        }}>
          <span style={{ fontSize: 13, fontWeight: 500, flex: 1 }}>{selected.full_name}</span>
          <span style={{ fontSize: 11, color: "var(--on-variant)" }}>{selected.employee_id}</span>
          <button className="btn btn-ghost" style={{ padding: "2px 8px", fontSize: 12 }} onClick={onClear}>
            <i className="ti ti-x" />
          </button>
        </div>
      ) : (
        <div style={{ position: "relative" }}>
          <input
            className="field-input"
            placeholder="Type 2+ characters to search…"
            value={search}
            onChange={e => onSearch(e.target.value)}
          />
          {searching && (
            <div style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)" }}>
              <i className="ti ti-loader-2 spin" style={{ color: "var(--on-variant)", fontSize: 14 }} />
            </div>
          )}
          {results.length > 0 && (
            <div style={{
              position: "absolute", top: "calc(100% + 2px)", left: 0, right: 0, zIndex: 60,
              background: "#fff", border: "1px solid var(--outline-v)", borderRadius: 8,
              boxShadow: "0 4px 16px rgba(0,0,0,0.10)", overflow: "hidden",
            }}>
              {results.map(emp => (
                <button
                  key={emp.uuid}
                  style={{
                    display: "block", width: "100%", padding: "9px 12px",
                    background: "none", border: "none", cursor: "pointer",
                    textAlign: "left", borderBottom: "1px solid var(--outline-v)",
                  }}
                  onClick={() => { onSelect(emp); onSearch(""); }}
                  onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-mid)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "none")}
                >
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{emp.full_name}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                    {emp.employee_id} · {emp.department}
                  </div>
                </button>
              ))}
            </div>
          )}
          {search.trim().length >= 2 && !searching && results.length === 0 && (
            <div style={{
              position: "absolute", top: "calc(100% + 2px)", left: 0, right: 0, zIndex: 60,
              background: "#fff", border: "1px solid var(--outline-v)", borderRadius: 8,
              padding: "12px 14px", fontSize: 13, color: "var(--on-variant)",
              boxShadow: "0 4px 16px rgba(0,0,0,0.10)",
            }}>
              No employees found.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Override Editor Modal ───────────────────────────────────────────────────

interface OverrideEditorProps {
  row:          WorkflowMatrixRow;
  employeeCode: string;
  onSaved:      (updated: WorkflowMatrixRow) => void;
  onClose:      () => void;
}

function OverrideEditor({ row, employeeCode, onSaved, onClose }: OverrideEditorProps) {
  const [l1Search,   setL1Search]   = useState("");
  const [l2Search,   setL2Search]   = useState("");
  const [l1Selected, setL1Selected] = useState<EmployeeResult | null>(null);
  const [l2Selected, setL2Selected] = useState<EmployeeResult | null>(null);
  const [saving,     setSaving]     = useState(false);
  const [apiError,   setApiError]   = useState("");

  const l1Url = l1Search.trim().length >= 2
    ? `${API.employees.list}?search=${encodeURIComponent(l1Search.trim())}&page_size=6`
    : null;
  const l2Url = l2Search.trim().length >= 2
    ? `${API.employees.list}?search=${encodeURIComponent(l2Search.trim())}&page_size=6`
    : null;

  const { data: l1Data, loading: l1Searching } = useFetch<ListResponse>(l1Url);
  const { data: l2Data, loading: l2Searching } = useFetch<ListResponse>(l2Url);

  const l1Results = l1Data?.results ?? [];
  const l2Results = l2Data?.results ?? [];

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
        l1_override_id: l1Selected ? l1Selected.uuid : null,
        l2_override_id: l2Selected ? l2Selected.uuid : null,
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
              Leave a level blank to keep the global default
              (<strong>{row.l1_approver_label}</strong>
              {row.l2_approver_role && <> / <strong>{row.l2_approver_label}</strong></>}).
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <EmployeeSearchInput
              label={`L1 Override (default: ${row.l1_approver_label})`}
              search={l1Search}
              onSearch={setL1Search}
              selected={l1Selected}
              onSelect={setL1Selected}
              onClear={() => setL1Selected(null)}
              results={l1Results}
              searching={l1Searching}
            />
            {row.l2_approver_role && (
              <EmployeeSearchInput
                label={`L2 Override (default: ${row.l2_approver_label})`}
                search={l2Search}
                onSearch={setL2Search}
                selected={l2Selected}
                onSelect={setL2Selected}
                onClear={() => setL2Selected(null)}
                results={l2Results}
                searching={l2Searching}
              />
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

function ApproverCell({ overrideId, overrideName, roleLabel }: {
  overrideId:   string | null;
  overrideName: string | null;
  roleLabel:    string;
}) {
  if (overrideId && overrideName) {
    return (
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{overrideName}</div>
        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Specific person</div>
      </div>
    );
  }
  return (
    <div>
      <div style={{ fontSize: 13, color: "var(--on-variant)" }}>{roleLabel}</div>
      <div style={{ fontSize: 11, color: "var(--outline)" }}>Global default</div>
    </div>
  );
}

// ─── Main Tab ─────────────────────────────────────────────────────────────────

interface Props {
  employeeCode: string;
}

export function ApprovalMatrixTab({ employeeCode }: Props) {
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

  const rows = data ?? [];

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
            {rows.map(row => (
              <tr key={row.workflow_type} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                <td style={{ padding: "14px 12px", fontWeight: 500, color: "var(--on-bg)" }}>
                  {row.workflow_label}
                </td>
                <td style={{ padding: "14px 12px" }}>
                  <ApproverCell
                    overrideId={row.l1_override_id}
                    overrideName={row.l1_override_name}
                    roleLabel={row.l1_approver_label}
                  />
                </td>
                <td style={{ padding: "14px 12px" }}>
                  {row.l2_approver_role ? (
                    <ApproverCell
                      overrideId={row.l2_override_id}
                      overrideName={row.l2_override_name}
                      roleLabel={row.l2_approver_label}
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
          onSaved={handleSaved}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
