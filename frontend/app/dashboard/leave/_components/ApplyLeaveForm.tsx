"use client";

// Compact "Leave request" modal, matching the reference layout exactly:
// Leave type / Duration, From / To, Reason / Balance preview, then the
// shared RequestModal footer. Leave type options come from the real,
// DB-configured LeavePolicy rows (GET /leave/policy/) — all 8 of them
// (casual/earned/sick/lwp/maternity/paternity/bereavement/comp_off), not
// a hardcoded frontend subset.

import { useState, useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import RequestModal from "@/components/RequestModal";
import Modal from "@/components/Modal";
import { getLeaveYear } from "@/lib/fiscalYear";
import {
  LeaveBalance, LeavePolicy, LeavePreview, LeaveRequest,
  calcWorkingDays,
} from "../_data";
import { type LeaveForm, BLANK } from "./applyLeaveFormHelpers";
import LeaveSubmittedScreen from "./LeaveSubmittedScreen";

const DURATION_OPTIONS = [
  { value: "full_day" as const,       label: "Full day"   },
  { value: "half_morning" as const,   label: "First half" },
  { value: "half_afternoon" as const, label: "Second half" },
];

export default function ApplyLeaveForm({ onCancel }: { onCancel: () => void }) {
  const [form,       setForm]       = useState<LeaveForm>(BLANK);
  const [reasonErr,  setReasonErr]  = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [submitted,  setSubmitted]  = useState<LeaveRequest | null>(null);

  const currentYear = getLeaveYear();
  const { data: balances } = useFetch<LeaveBalance[]>(API.leave.balance + `?year=${currentYear}`);
  const { data: policies } = useFetch<LeavePolicy[]>(API.leave.policy);

  const balanceMap  = Object.fromEntries((balances ?? []).map(b => [b.leave_type, b]));
  const leaveOptions = (policies ?? []).filter(p => p.is_active);
  const balance     = balanceMap[form.leave_type];
  const isHalfDay   = form.duration !== "full_day";
  const toDate      = isHalfDay ? form.from_date : form.to_date;

  const workDays = useMemo(
    () => calcWorkingDays(form.from_date, toDate, form.duration, false),
    [form.from_date, toDate, form.duration]
  );

  const previewUrl = (form.leave_type && form.from_date && toDate)
    ? `${API.leave.requests}?action=preview`
      + `&leave_type=${encodeURIComponent(form.leave_type)}`
      + `&start_date=${encodeURIComponent(form.from_date)}`
      + `&end_date=${encodeURIComponent(toDate)}`
      + `&duration=${encodeURIComponent(form.duration)}`
    : null;
  const { data: preview } = useFetch<LeavePreview>(previewUrl);

  const requestedDays = preview?.actual_leave_days ?? (workDays > 0 ? workDays : 0);
  const available     = balance ? Number(balance.available_days) : null;
  const insufficientBalance = !!preview && !preview.sufficient_balance && !preview.lop_enabled;

  function setField<K extends keyof LeaveForm>(key: K, val: LeaveForm[K]) {
    setForm(prev => ({ ...prev, [key]: val }));
  }

  function validate(): boolean {
    setError(null);
    setReasonErr(null);
    if (!form.from_date) { setError("Please select a start date."); return false; }
    if (!isHalfDay && !form.to_date) { setError("Please select an end date."); return false; }
    if (!isHalfDay && form.to_date < form.from_date) { setError("End date must be on or after start date."); return false; }
    if (form.reason.trim().length < 10) { setReasonErr("Reason must be at least 10 characters."); return false; }
    if (insufficientBalance) { setError("Insufficient leave balance for the selected dates."); return false; }
    return true;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("leave_type", form.leave_type);
      fd.append("duration",   form.duration);
      fd.append("start_date", form.from_date);
      fd.append("end_date",   toDate);
      fd.append("reason",     form.reason);
      const res = await clientApi.post(API.leave.requests, fd);
      setSubmitted(res.data.data as LeaveRequest);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg || "Failed to submit leave request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <Modal title="Leave request" onClose={onCancel} size="lg" bodyStyle={{ padding: 0 }}>
        <LeaveSubmittedScreen
          submitted={submitted}
          leaveType={form.leave_type}
          onApplyAnother={() => { setForm(BLANK); setSubmitted(null); }}
          onCancel={onCancel}
        />
      </Modal>
    );
  }

  const balancePreviewText = form.duration && available !== null
    ? `${available} days available · ${requestedDays || 0} day${requestedDays === 1 ? "" : "s"} requested`
    : requestedDays
      ? `No balance tracked · ${requestedDays} day${requestedDays === 1 ? "" : "s"} requested`
      : "Select dates to preview";

  return (
    <RequestModal
      title="Leave request"
      onClose={onCancel}
      onSubmit={handleSubmit}
      submitting={submitting}
      error={error}
      submitLabel="Submit request"
    >
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Leave type</label>
          <select
            className="field-input field-select"
            value={form.leave_type}
            onChange={e => setField("leave_type", e.target.value as LeaveForm["leave_type"])}
          >
            {leaveOptions.map(p => (
              <option key={p.leave_type} value={p.leave_type}>{p.leave_type_display}</option>
            ))}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Duration</label>
          <select
            className="field-input field-select"
            value={form.duration}
            onChange={e => setField("duration", e.target.value as LeaveForm["duration"])}
          >
            {DURATION_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">From</label>
          <input
            type="date" className="field-input"
            value={form.from_date}
            onChange={e => setField("from_date", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">To</label>
          <input
            type="date" className="field-input"
            value={toDate}
            min={form.from_date}
            disabled={isHalfDay}
            onChange={e => setField("to_date", e.target.value)}
            style={isHalfDay ? { opacity: 0.5, cursor: "not-allowed" } : undefined}
          />
        </div>
      </div>

      <div className="form-row cols-2">
        <div className="field-group">
          <label className="field-label">Reason</label>
          <textarea
            className="field-input"
            rows={3}
            value={form.reason}
            onChange={e => setField("reason", e.target.value)}
            placeholder="Reason for leave"
          />
          {reasonErr && <p style={{ fontSize: 11, color: "var(--error)", marginTop: 4 }}>{reasonErr}</p>}
        </div>
        <div className="field-group">
          <label className="field-label">Balance preview</label>
          <div
            style={{
              fontSize: 13, color: "var(--on-bg)", background: "var(--bg-low)",
              border: "1px solid var(--outline-v)", borderRadius: "var(--radius)",
              padding: "10px 14px", minHeight: 76, display: "flex", alignItems: "center",
            }}
          >
            {balancePreviewText}
          </div>
        </div>
      </div>
    </RequestModal>
  );
}
