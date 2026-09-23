"use client";

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import EmptyState from "@/components/EmptyState";
import LoadingState from "@/components/LoadingState";
import type { WorkflowMatrixRow } from "@/types/approvalMatrix";
import RelationshipEditorModal from "./RelationshipEditorModal";
import OverrideEditor from "./OverrideEditor";

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
            background: "rgba(124,58,237,0.10)", color: "var(--primary)",
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
  // True only when this reporting manager was resolved from an actual
  // placed chief in the employee's Org Unit chain (backend
  // User.reporting_manager_from_org_chart) — false covers both the
  // branch-wide fallback and a manually-picked manager. Purely
  // informational, surfaced here so gaps in the org chart (missing chiefs)
  // are visible instead of silently masked by a working fallback.
  defaultManagerFromOrgChart?: boolean;
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
  defaultManagerFromOrgChart = false,
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
  const [managerFromOrgChart, setManagerFromOrgChart] = useState(defaultManagerFromOrgChart);
  const [hrId,        setHrId]        = useState(defaultHrId);
  const [hrName,      setHrName]      = useState(defaultHrName);

  const [editingManager, setEditingManager] = useState(false);
  const [editingHr,      setEditingHr]      = useState(false);

  const canEdit = usePermission("settings.edit");

  function handleSaved(_updated: WorkflowMatrixRow) {
    refetch();
    setEditing(null);
  }

  const branchParam = branch ? `?branch=${encodeURIComponent(branch)}` : "";

  if (loading) {
    return <LoadingState label="Loading approval matrix…" />;
  }

  if (error) {
    return (
      <div className="alert alert-error">
        <i className="ti ti-alert-circle" /> {error}
      </div>
    );
  }

  const ACTIVE_WORKFLOWS = new Set(["leave", "expense", "attendance_correction"]);
  const rows = (data ?? []).filter(r => ACTIVE_WORKFLOWS.has(r.workflow_type as string));

  return (
    <>
      {/* ── Reporting Relationships card ── */}
      <div className="settings-card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div>
            <div className="settings-card-title" style={{ marginBottom: 2 }}>Reporting Relationships</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Used as the default approvers for all workflows unless overridden below
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
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", display: "flex", alignItems: "center", gap: 6 }}>
                    {managerName}
                    {!managerFromOrgChart && (
                      <span
                        className="badge badge-warn"
                        style={{ fontSize: 9.5, fontWeight: 650, padding: "2px 7px" }}
                        title="Not resolved from a placed chief in this employee's Org Unit chain — either the org chart has no chief set for that chain yet, or this was picked manually."
                      >
                        Not from org chart
                      </span>
                    )}
                  </div>
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
            By default the global role rules apply. Override below to assign a specific person for this employee.
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
                  <td colSpan={canEdit ? 4 : 3}>
                    <EmptyState icon="ti-list-check" title="No approval matrix configured" />
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
            // A manual pick here is never org-chart-derived — matches the
            // backend, which resets reporting_manager_from_org_chart to
            // False on this same endpoint (EmployeeReportingManagerView.patch).
            setManagerFromOrgChart(false);
            setEditingManager(false);
            onManagerChanged?.(id, name);
          }}
          onClose={() => setEditingManager(false)}
        />
      )}

      {editingHr && (
        <RelationshipEditorModal
          title="Edit Company Code HR"
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
