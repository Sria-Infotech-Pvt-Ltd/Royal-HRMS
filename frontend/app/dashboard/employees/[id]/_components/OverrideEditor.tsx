"use client";

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import Modal from "@/components/Modal";
import type { WorkflowMatrixRow, ApprovalWorkflowType } from "@/types/approvalMatrix";
import { type PickerEmployee, SELECT_CLS, SELECT_STYLE } from "./approvalMatrixShared";

interface OverrideEditorProps {
  row:              WorkflowMatrixRow;
  employeeCode:     string;
  branch:           string;
  defaultManagerId: string;
  defaultHrId:      string;
  onSaved:          (updated: WorkflowMatrixRow) => void;
  onClose:          () => void;
}

export default function OverrideEditor({ row, employeeCode, branch, defaultManagerId, defaultHrId, onSaved, onClose }: OverrideEditorProps) {
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
    <Modal
      title={<>Override Approvers — {row.workflow_label}</>}
      onClose={onClose}
      maxWidth={480}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save Override"}
          </button>
        </>
      }
    >
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
    </Modal>
  );
}
