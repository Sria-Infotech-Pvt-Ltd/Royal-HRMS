"use client";

import { useState, useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { getLeaveYear } from "@/lib/fiscalYear";
import {
  LeaveBalance, LeavePolicy, LeavePreview, LeaveRequest,
  LEAVE_TYPE_CONFIG, calcWorkingDays,
  type DurationKey,
} from "../_data";
import { type LeaveForm, BLANK, Lbl, Err } from "./applyLeaveFormHelpers";
import LeaveSubmittedScreen from "./LeaveSubmittedScreen";
import LeaveTypePicker from "./LeaveTypePicker";
import LeaveDurationDates from "./LeaveDurationDates";
import LeaveRequestSummary from "./LeaveRequestSummary";
import LeaveSupportingDocument from "./LeaveSupportingDocument";
import LeaveHandoverFields from "./LeaveHandoverFields";

export default function ApplyLeaveForm({ onCancel }: { onCancel: () => void }) {
  const { showToast } = useToast();
  const [form,          setForm]          = useState<LeaveForm>(BLANK);
  const [errors,        setErrors]        = useState<Record<string, string>>({});
  const [submitting,    setSubmitting]    = useState(false);
  const [submitted,     setSubmitted]     = useState<LeaveRequest | null>(null);
  const [docFile,       setDocFile]       = useState<File | null>(null);

  const currentYear = getLeaveYear();
  const { data: balances } = useFetch<LeaveBalance[]>(API.leave.balance + `?year=${currentYear}`);
  const { data: policies } = useFetch<LeavePolicy[]>(API.leave.policy);

  const balanceMap = Object.fromEntries((balances ?? []).map(b => [b.leave_type, b]));
  const policyMap  = Object.fromEntries((policies ?? []).map(p => [p.leave_type, p]));

  const ltConfig   = LEAVE_TYPE_CONFIG[form.leave_type];
  const balance    = balanceMap[form.leave_type];
  const policy     = policyMap[form.leave_type];
  const isHalfDay       = form.duration !== "full_day";
  const sandwichEnabled = policy?.sandwich_leave_enabled ?? false;
  const workDays        = useMemo(
    () => calcWorkingDays(form.from_date, form.to_date, form.duration, sandwichEnabled),
    [form.from_date, form.to_date, form.duration, sandwichEnabled]
  );
  const available     = balance ? Number(balance.available_days) : 0;
  const convertToLop   = policy?.convert_to_lop ?? false;
  const exceedsBalance = !ltConfig.isLwp && workDays > available && workDays > 0;
  // With convert_to_lop on, exceeding balance is allowed — the shortfall is
  // processed as LOP by the backend rather than blocking submission. This is
  // only the instant client estimate; once the server preview loads it takes over.
  const overLimit = exceedsBalance && !convertToLop;

  // Server-side preview — fires once leave_type, start_date, and end_date are
  // all selected. Gives the authoritative breakdown (holidays, week-offs,
  // balance) that the client-side calcWorkingDays estimate above can't see.
  const previewEndDate = isHalfDay ? form.from_date : form.to_date;
  const canPreview      = !!(form.leave_type && form.from_date && previewEndDate);
  const previewUrl = canPreview
    ? `${API.leave.requests}?action=preview`
      + `&leave_type=${encodeURIComponent(form.leave_type)}`
      + `&start_date=${encodeURIComponent(form.from_date)}`
      + `&end_date=${encodeURIComponent(previewEndDate)}`
      + `&duration=${encodeURIComponent(form.duration)}`
    : null;
  const { data: preview, loading: previewLoading } = useFetch<LeavePreview>(previewUrl);

  const insufficientBalance = !!preview && !preview.sufficient_balance && !preview.lop_enabled;

  function setField<K extends keyof LeaveForm>(key: K, val: LeaveForm[K]) {
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });
    setForm(prev => ({ ...prev, [key]: val }));
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!form.from_date)                                    e.from_date = "Start date is required.";
    if (!isHalfDay && !form.to_date)                        e.to_date   = "End date is required.";
    if (!isHalfDay && form.from_date && form.to_date && form.to_date < form.from_date)
                                                            e.to_date   = "End date must be on or after start date.";
    if (!form.reason.trim())                                e.reason    = "Please provide a reason.";
    if (form.reason.trim().length < 10)                     e.reason    = "Reason must be at least 10 characters.";
    if (ltConfig.requiresDoc && !docFile)                   e.doc       = "Supporting document is required for this leave type.";
    // Once the server preview has loaded, it's authoritative — defer to
    // insufficientBalance below instead of this local, holiday-blind estimate.
    if (!preview && overLimit)                              e.from_date = `Only ${available} working day(s) available.`;
    if (workDays <= 0 && form.from_date)                    e.from_date = "Selected date range has no working days.";
    if (insufficientBalance)                                e.from_date = "Insufficient leave balance for the selected dates.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("leave_type",          form.leave_type);
      fd.append("duration",            form.duration);
      fd.append("start_date",          form.from_date);
      fd.append("end_date",            isHalfDay ? form.from_date : form.to_date);
      fd.append("reason",              form.reason);
      fd.append("contact_during_leave", form.contact_during_leave);
      fd.append("handover_to",         form.handover_to);
      fd.append("handover_notes",      form.handover_notes);
      if (docFile) fd.append("document", docFile);

      const res = await clientApi.post(API.leave.requests, fd);
      setSubmitted(res.data.data as LeaveRequest);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to submit leave request. Please try again.", "error");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Success screen ───────────────────────────────────────────────────────────

  if (submitted) {
    return (
      <LeaveSubmittedScreen
        submitted={submitted}
        leaveType={form.leave_type}
        onApplyAnother={() => { setForm(BLANK); setDocFile(null); setSubmitted(null); }}
        onCancel={onCancel}
      />
    );
  }

  function handleDurationChange(value: DurationKey) {
    setField("duration", value);
    if (value !== "full_day") setField("to_date", "");
  }

  return (
    <div className="p-6">
      <div className="leave-request-layout">
        <div className="flex min-w-0 flex-col gap-6">
          <div>
            <Lbl text="Leave type" required />
            <LeaveTypePicker selected={form.leave_type} balanceMap={balanceMap} onSelect={key => setField("leave_type", key)} />
            {policy?.policy_note && (
              <p className="mt-2.5 flex items-start gap-1.5 text-xs text-[var(--on-variant)]">
                <i className="ti ti-info-circle mt-px flex-shrink-0" /> {policy.policy_note}
              </p>
            )}
          </div>

          <LeaveDurationDates
            form={form}
            errors={errors}
            isHalfDay={isHalfDay}
            onDurationChange={handleDurationChange}
            onDateChange={(field, isoDate) => setField(field, isoDate)}
          />

          <div>
            <Lbl text="Reason" required />
            <textarea
              className={`field-input${errors.reason ? " field-error" : ""}`}
              value={form.reason}
              onChange={event => setField("reason", event.target.value)}
              placeholder="Briefly describe the reason for your leave"
              rows={3}
              maxLength={500}
              style={{ resize: "none" }}
            />
            <div className="mt-1 flex justify-between">
              <Err msg={errors.reason} />
              <span className={`ml-auto text-xs ${form.reason.length > 450 ? "text-[var(--warn)]" : "text-[var(--on-variant)]"}`}>{form.reason.length}/500</span>
            </div>
          </div>

          <LeaveSupportingDocument file={docFile} isRequired={ltConfig.requiresDoc} error={errors.doc} onChange={setDocFile} />

          <LeaveHandoverFields form={form} onChange={setField} />
        </div>

        <LeaveRequestSummary
          leaveType={ltConfig}
          balance={balance}
          available={available}
          form={form}
          isHalfDay={isHalfDay}
          workDays={workDays}
          isOverLimit={overLimit}
          preview={preview}
          isPreviewLoading={previewLoading && canPreview}
          isInsufficientBalance={insufficientBalance}
        />
      </div>

      <div className="mt-6 flex items-center justify-end gap-2.5 border-t border-[var(--outline-v)] pt-4">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="button" className="btn btn-filled" onClick={handleSubmit} disabled={submitting || insufficientBalance}>
          {submitting ? <><i className="ti ti-loader-2 spin" /> Submitting…</> : "Submit request"}
        </button>
      </div>
    </div>
  );
}
