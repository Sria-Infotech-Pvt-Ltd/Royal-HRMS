"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import SearchableSelect from "@/components/SearchableSelect";
import Modal from "@/components/Modal";
import type { InvalidPunch } from "@/types/attendance";

interface HrUser {
  id:          string;
  employee_id: string;
  full_name:   string;
}

interface Props {
  punch:      InvalidPunch;
  onClose:    () => void;
  onAssigned: () => void;
}

export default function AssignPunchModal({ punch, onClose, onAssigned }: Props) {
  const { showToast } = useToast();
  const { data: hrUsers } = useFetch<HrUser[]>(API.employees.hrList);
  const [assignedTo, setAssignedTo] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState<string | null>(null);

  async function handleSubmit() {
    if (!assignedTo) { setError("Please select an HR user."); return; }
    setSubmitting(true);
    setError(null);
    try {
      await clientApi.post(API.attendance.invalidPunchAssign(punch.id), { assigned_to: assignedTo });
      showToast("Invalid punch assigned.", "success");
      onAssigned();
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? "Failed to assign invalid punch.";
      setError(message);
      showToast(message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      title={
        <>
          <i className="ti ti-user-check" style={{ marginRight: 8, color: "var(--primary)" }} />
          Assign Invalid Punch
        </>
      }
      onClose={onClose}
      maxWidth={420}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting}>
            {submitting ? <><i className="ti ti-loader-2" /> Assigning…</> : "Assign"}
          </button>
        </>
      }
    >
          {error && (
            <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> <span>{error}</span></div>
          )}

          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 12 }}>
            Device: {punch.device_id} · {punch.raw_time}
          </div>

          <div className="field-group">
            <label className="field-label">Assign to HR user</label>
            <SearchableSelect
              inputClassName="field-input"
              value={assignedTo}
              onChange={setAssignedTo}
              placeholder="Select HR user…"
              options={(hrUsers ?? []).map(u => ({ value: u.id, label: `${u.full_name} (${u.employee_id})` }))}
            />
          </div>
    </Modal>
  );
}
