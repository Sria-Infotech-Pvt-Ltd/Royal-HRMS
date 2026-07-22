"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";

const STATUSES = [
  { value: "present",    label: "Present"    },
  { value: "late",       label: "Late Arrival"},
  { value: "half_day",   label: "Half Day"   },
  { value: "on_leave",   label: "On Leave"   },
  { value: "absent",     label: "Absent"     },
  { value: "weekly_off", label: "Week Off"   },
  { value: "holiday",    label: "Holiday"    },
  { value: "incomplete", label: "Incomplete" },
];

// ── Edit existing record ──────────────────────────────────────────────────────

interface EditProps {
  recordId: string;
  initialStatus: string;
  initialClockIn: string;
  initialClockOut: string;
  initialNote: string;
  onSaved: () => void;
  onCancel: () => void;
}

export function AttendanceEditForm({
  recordId, initialStatus, initialClockIn, initialClockOut, initialNote,
  onSaved, onCancel,
}: EditProps) {
  const { showToast } = useToast();
  const [status,   setStatus]   = useState(initialStatus);
  const [clockIn,  setClockIn]  = useState(initialClockIn ?? "");
  const [clockOut, setClockOut] = useState(initialClockOut ?? "");
  const [note,     setNote]     = useState(initialNote ?? "");
  const [reason,   setReason]   = useState("");
  const [saving,   setSaving]   = useState(false);

  async function handleSave() {
    if (!reason.trim()) {
      showToast("Reason is required — it's recorded in the audit log.", "error");
      return;
    }
    setSaving(true);
    try {
      await clientApi.patch(API.attendance.record(recordId), {
        status,
        clock_in:  clockIn  || null,
        clock_out: clockOut || null,
        note,
        reason,
      });
      showToast("Attendance record updated.", "success");
      onSaved();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? "Failed to save. Please try again.";
      showToast(msg, "error");
    } finally {
      setSaving(false);
    }
  }

  return <AttendanceFormFields
    status={status} clockIn={clockIn} clockOut={clockOut} note={note} reason={reason}
    onStatus={setStatus} onClockIn={setClockIn} onClockOut={setClockOut}
    onNote={setNote} onReason={setReason}
    saving={saving} onSave={handleSave} onCancel={onCancel}
    saveLabel="Save Changes"
  />;
}

// ── Create new record ─────────────────────────────────────────────────────────

interface CreateProps {
  employeeId: string;
  date: string;
  onSaved: (recordId: string) => void;
  onCancel: () => void;
}

export function AttendanceCreateForm({ employeeId, date, onSaved, onCancel }: CreateProps) {
  const { showToast } = useToast();
  const [status,   setStatus]   = useState("present");
  const [clockIn,  setClockIn]  = useState("");
  const [clockOut, setClockOut] = useState("");
  const [note,     setNote]     = useState("");
  const [reason,   setReason]   = useState("");
  const [saving,   setSaving]   = useState(false);

  async function handleSave() {
    if (!reason.trim()) {
      showToast("Reason is required — it's recorded in the audit log.", "error");
      return;
    }
    setSaving(true);
    try {
      const response = await clientApi.post(API.attendance.recordCreate, {
        employee_id: employeeId,
        date,
        status,
        clock_in:  clockIn  || null,
        clock_out: clockOut || null,
        note,
        reason,
      });
      showToast("Attendance record created.", "success");
      onSaved((response.data as { data?: { record_id?: string } })?.data?.record_id ?? "");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? "Failed to create record. Please try again.";
      showToast(msg, "error");
    } finally {
      setSaving(false);
    }
  }

  return <AttendanceFormFields
    status={status} clockIn={clockIn} clockOut={clockOut} note={note} reason={reason}
    onStatus={setStatus} onClockIn={setClockIn} onClockOut={setClockOut}
    onNote={setNote} onReason={setReason}
    saving={saving} onSave={handleSave} onCancel={onCancel}
    saveLabel="Create Record"
  />;
}

// ── Shared form fields ────────────────────────────────────────────────────────

interface FieldsProps {
  status: string; clockIn: string; clockOut: string;
  note: string; reason: string;
  onStatus: (v: string) => void; onClockIn: (v: string) => void;
  onClockOut: (v: string) => void; onNote: (v: string) => void;
  onReason: (v: string) => void;
  saving: boolean; onSave: () => void; onCancel: () => void;
  saveLabel: string;
}

function AttendanceFormFields({
  status, clockIn, clockOut, note, reason,
  onStatus, onClockIn, onClockOut, onNote, onReason,
  saving, onSave, onCancel, saveLabel,
}: FieldsProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div>
        <label className="field-label">Status</label>
        <select className="field-input" value={status} onChange={e => onStatus(e.target.value)}>
          {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>

      <div className="form-row cols-2">
        <div>
          <label className="field-label">Clock In</label>
          <input type="time" className="field-input" value={clockIn} onChange={e => onClockIn(e.target.value)} />
        </div>
        <div>
          <label className="field-label">Clock Out</label>
          <input type="time" className="field-input" value={clockOut} onChange={e => onClockOut(e.target.value)} />
        </div>
      </div>

      <div>
        <label className="field-label">Note (optional)</label>
        <input
          type="text" className="field-input" maxLength={200}
          placeholder="WFH, field work, biometric failure…"
          value={note} onChange={e => onNote(e.target.value)}
        />
      </div>

      <div>
        <label className="field-label">
          Reason <span style={{ color: "var(--error)" }}>*</span>
          <span style={{ fontSize: 10, color: "var(--on-variant)", fontWeight: 400, marginLeft: 6 }}>logged in audit trail</span>
        </label>
        <textarea
          className="field-input" rows={2} maxLength={500}
          placeholder="e.g. Biometric device failure, employee forgot to punch, client visit…"
          value={reason} onChange={e => onReason(e.target.value)}
          style={{ resize: "vertical" }}
        />
      </div>

      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", paddingTop: 4 }}>
        <button className="btn btn-ghost btn-sm" onClick={onCancel} disabled={saving}>Cancel</button>
        <button className="btn btn-filled btn-sm" onClick={onSave} disabled={saving}>
          {saving ? <><i className="ti ti-loader-2 animate-spin" /> Saving…</> : <><i className="ti ti-check" /> {saveLabel}</>}
        </button>
      </div>
    </div>
  );
}
