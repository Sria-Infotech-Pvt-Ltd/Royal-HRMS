"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import type { GlobalApprovalRule, ApprovalWorkflowType, ApprovalRulePerson } from "@/types/approvalMatrix";
import { buildApproverOptions, fromSelectValue, toSelectValue } from "@/lib/approvalRuleOptions";
import Modal from "@/components/Modal";
import SearchableSelect from "@/components/SearchableSelect";

const WORKFLOW_ICONS: Record<string, string> = {
  leave:                 "ti-beach",
  expense:               "ti-wallet",
  attendance_correction: "ti-clock-edit",
  timesheet:             "ti-clock-check",
};

interface EditState {
  workflow_type:  ApprovalWorkflowType;
  workflow_label: string;
  /** Dropdown values: "reporting_manager", "hr", "person:<id>" or "". */
  l1_choice:      string;
  l2_choice:      string;
  eligible:       ApprovalRulePerson[];
  l1_saved:       { userId: string | null; label: string } | null;
  l2_saved:       { userId: string | null; label: string } | null;
}

export default function ApprovalRulesPage() {
  const router = useRouter();

  const { data, loading, error, refetch } = useFetch<GlobalApprovalRule[]>(API.settings.approvalRules);

  const [editing,  setEditing]  = useState<EditState | null>(null);
  const [saving,   setSaving]   = useState(false);
  const [apiError, setApiError] = useState("");

  const rules = data ?? [];

  function openEdit(rule: GlobalApprovalRule) {
    setEditing({
      workflow_type:  rule.workflow_type,
      workflow_label: rule.workflow_label,
      l1_choice:      toSelectValue(rule.l1_approver_kind, rule.l1_approver_user_id),
      l2_choice:      toSelectValue(rule.l2_approver_kind, rule.l2_approver_user_id),
      eligible:       rule.eligible_approvers ?? [],
      l1_saved:       { userId: rule.l1_approver_user_id, label: rule.l1_approver_label },
      l2_saved:       { userId: rule.l2_approver_user_id, label: rule.l2_approver_label },
    });
    setApiError("");
  }

  async function handleSave() {
    if (!editing) return;
    setSaving(true);
    setApiError("");
    try {
      const l1 = fromSelectValue(editing.l1_choice);
      const l2 = fromSelectValue(editing.l2_choice);
      await clientApi.patch(API.settings.approvalRules, {
        workflow_type:    editing.workflow_type,
        l1_approver_kind: l1.kind,
        l1_approver_user: l1.userId,
        l2_approver_kind: l2.kind,
        l2_approver_user: l2.userId,
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
          <div className="page-title">Approval Rules</div>
          <div className="page-sub">Configure who approves each workflow — globally, with per-employee overrides on the employee profile.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
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
                  <th style={{ textAlign: "left", padding: "10px 14px", color: "var(--on-variant)", fontWeight: 600 }}>L1 approver</th>
                  <th style={{ textAlign: "left", padding: "10px 14px", color: "var(--on-variant)", fontWeight: 600 }}>L2 approver</th>
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
                          background: "var(--primary-c, rgba(124,58,237,0.10))",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          flexShrink: 0,
                        }}>
                          <i className={`ti ${WORKFLOW_ICONS[rule.workflow_type] ?? "ti-check"}`} style={{ color: "var(--primary)", fontSize: 15 }} />
                        </div>
                        <span style={{ fontWeight: 500, color: "var(--on-bg)" }}>{rule.workflow_label}</span>
                      </div>
                    </td>
                    <td style={{ padding: "14px", color: "var(--on-bg)" }}>
                      {rule.l1_approver_label || <span style={{ opacity: 0.5, color: "var(--on-variant)" }}>Not set</span>}
                    </td>
                    <td style={{ padding: "14px", color: rule.l2_approver_kind ? "var(--on-bg)" : "var(--on-variant)" }}>
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
        <Modal
          title={`Edit Rule — ${editing.workflow_label}`}
          onClose={() => setEditing(null)}
          maxWidth={440}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>Cancel</button>
              <button
                className="btn btn-primary"
                onClick={handleSave}
                disabled={saving || !editing.l1_choice}
              >
                {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save Rule"}
              </button>
            </>
          }
        >
          {apiError && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" /> {apiError}
            </div>
          )}

          <div className="field-group mb-16">
            <label className="field-label">L1 approver *</label>
            <SearchableSelect
              value={editing.l1_choice}
              onChange={v => setEditing(prev => prev ? { ...prev, l1_choice: v } : prev)}
              placeholder="— Select who approves —"
              options={buildApproverOptions(editing.eligible, editing.l1_saved)}
              inputClassName="field-input"
            />
          </div>

          <div className="field-group">
            <label className="field-label">
              L2 approver{" "}
              <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>(leave blank for single-level)</span>
            </label>
            <SearchableSelect
              value={editing.l2_choice}
              onChange={v => setEditing(prev => prev ? { ...prev, l2_choice: v } : prev)}
              placeholder="— Single level (no L2) —"
              options={buildApproverOptions(editing.eligible, editing.l2_saved)}
              inputClassName="field-input"
            />
          </div>
        </Modal>
      )}
    </div>
  );
}
