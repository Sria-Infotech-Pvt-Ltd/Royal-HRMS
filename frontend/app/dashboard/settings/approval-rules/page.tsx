"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import type { GlobalApprovalRule, ApprovalWorkflowType, ApproverRole } from "@/types/approvalMatrix";

const WORKFLOW_ICONS: Record<string, string> = {
  leave:       "ti-beach",
  expense:     "ti-wallet",
  resignation: "ti-logout",
  loan:        "ti-coin",
};

const APPROVER_ROLE_OPTIONS: { value: ApproverRole; label: string }[] = [
  { value: "reporting_manager", label: "Reporting Manager" },
  { value: "hr_manager",        label: "HR Manager" },
  { value: "admin",             label: "Admin" },
];

interface EditState {
  workflow_type:   ApprovalWorkflowType;
  workflow_label:  string;
  l1_approver_role: ApproverRole;
  l2_approver_role: ApproverRole | "";
}

export default function ApprovalRulesPage() {
  const router = useRouter();

  const { data, loading, error, refetch } = useFetch<GlobalApprovalRule[]>(API.settings.approvalRules);

  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving,  setSaving]  = useState(false);
  const [apiError, setApiError] = useState("");

  const rules = data ?? [];

  function openEdit(rule: GlobalApprovalRule) {
    setEditing({
      workflow_type:    rule.workflow_type,
      workflow_label:   rule.workflow_label,
      l1_approver_role: rule.l1_approver_role,
      l2_approver_role: rule.l2_approver_role,
    });
    setApiError("");
  }

  async function handleSave() {
    if (!editing) return;
    setSaving(true);
    setApiError("");
    try {
      await clientApi.patch(API.settings.approvalRules, {
        workflow_type:    editing.workflow_type,
        l1_approver_role: editing.l1_approver_role,
        l2_approver_role: editing.l2_approver_role,
      });
      refetch();
      setEditing(null);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiError(msg || "Failed to save rule.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <button
            className="btn btn-ghost"
            style={{ marginBottom: 8, fontSize: 13, padding: "4px 10px" }}
            onClick={() => router.push("/dashboard/settings")}
          >
            <i className="ti ti-arrow-left" /> Settings
          </button>
          <div className="page-title">Approval Rules</div>
          <div className="page-sub">Configure who approves each workflow type — globally, with per-employee overrides on the employee profile.</div>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-2 py-12 text-[13px] text-[var(--on-variant)]">
          <i className="ti ti-loader-2 animate-spin text-[20px]" style={{ color: "var(--primary)" }} />
          Loading rules…
        </div>
      )}

      {error && (
        <div className="alert alert-error">
          <i className="ti ti-alert-circle" /> {error}
        </div>
      )}

      {!loading && !error && (
        <div className="settings-card">
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--outline-v)" }}>
                  <th style={{ textAlign: "left", padding: "10px 14px", color: "var(--on-variant)", fontWeight: 600, width: "25%" }}>Workflow</th>
                  <th style={{ textAlign: "left", padding: "10px 14px", color: "var(--on-variant)", fontWeight: 600 }}>L1 Approver Role</th>
                  <th style={{ textAlign: "left", padding: "10px 14px", color: "var(--on-variant)", fontWeight: 600 }}>L2 Approver Role</th>
                  <th style={{ width: 80 }} />
                </tr>
              </thead>
              <tbody>
                {rules.map(rule => (
                  <tr key={rule.workflow_type} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                    <td style={{ padding: "14px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{
                          width: 32, height: 32, borderRadius: 8,
                          background: "var(--primary-c, rgba(30,78,140,0.10))",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          flexShrink: 0,
                        }}>
                          <i className={`ti ${WORKFLOW_ICONS[rule.workflow_type] ?? "ti-check"}`} style={{ color: "var(--primary)", fontSize: 15 }} />
                        </div>
                        <span style={{ fontWeight: 500, color: "var(--on-bg)" }}>{rule.workflow_label}</span>
                      </div>
                    </td>
                    <td style={{ padding: "14px", color: "var(--on-bg)" }}>{rule.l1_approver_label}</td>
                    <td style={{ padding: "14px", color: rule.l2_approver_role ? "var(--on-bg)" : "var(--on-variant)" }}>
                      {rule.l2_approver_label || <span style={{ opacity: 0.5 }}>Single level</span>}
                    </td>
                    <td style={{ padding: "14px", textAlign: "right" }}>
                      <button
                        className="btn btn-ghost"
                        style={{ padding: "4px 12px", fontSize: 12 }}
                        onClick={() => openEdit(rule)}
                      >
                        <i className="ti ti-edit" /> Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {editing && (
        <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && setEditing(null)}>
          <div className="modal" style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <div className="modal-title">Edit Rule — {editing.workflow_label}</div>
              <button className="modal-close" onClick={() => setEditing(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              {apiError && (
                <div className="alert alert-error mb-16">
                  <i className="ti ti-alert-circle" /> {apiError}
                </div>
              )}

              <div className="field-group mb-16">
                <label className="field-label">L1 Approver Role *</label>
                <select
                  className="field-input field-select"
                  value={editing.l1_approver_role}
                  onChange={e => setEditing(prev => prev ? { ...prev, l1_approver_role: e.target.value as ApproverRole } : prev)}
                >
                  {APPROVER_ROLE_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              <div className="field-group">
                <label className="field-label">L2 Approver Role <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>(leave blank for single-level)</span></label>
                <select
                  className="field-input field-select"
                  value={editing.l2_approver_role}
                  onChange={e => setEditing(prev => prev ? { ...prev, l2_approver_role: e.target.value as ApproverRole | "" } : prev)}
                >
                  <option value="">— Single level (no L2) —</option>
                  {APPROVER_ROLE_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save Rule"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
