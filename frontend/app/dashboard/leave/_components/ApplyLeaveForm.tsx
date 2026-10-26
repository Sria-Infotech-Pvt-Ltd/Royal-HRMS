"use client";

import { useEffect, useState, useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { getLeaveYear } from "@/lib/fiscalYear";
import {
  LeaveBalance, LeavePolicy, LeavePreview, LeaveRequest,
  LEAVE_TYPE_CONFIG, LEAVE_TYPES_LIST, calcWorkingDays,
  type DurationKey,
} from "../_data";
import DateInput from "@/components/shared/DateInput";
import { type LeaveForm, BLANK, Err } from "./applyLeaveFormHelpers";
import LeaveSubmittedScreen from "./LeaveSubmittedScreen";
import LeaveSupportingDocument from "./LeaveSupportingDocument";
import LeaveHandoverFields from "./LeaveHandoverFields";

const DURATION_OPTIONS: { value: DurationKey; label: string }[] = [
  { value: "full_day",       label: "Full day" },
  { value: "half_morning",   label: "Morning half" },
  { value: "half_afternoon", label: "Afternoon half" },
];

/** Small uppercase field label — this compact layout's own style, distinct
 *  from the bold-sentence-case Lbl() the optional sections below still use. */
function SmallLbl({ text }: { text: string }) {
  return (
    <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-[var(--on-variant)]">
      {text}
    </div>
  );
}

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
  const policyMap  = useMemo(
    () => Object.fromEntries((policies ?? []).map(p => [p.leave_type, p])),
    [policies]
  );
  const availableLeaveTypes = useMemo(
    () => policies
      ? LEAVE_TYPES_LIST.filter(type => {
        const leavePolicy = policyMap[type.key];
        return leavePolicy?.is_active && leavePolicy.matches_gender_for_requester;
      })
      : LEAVE_TYPES_LIST,
    [policies, policyMap]
  );

  const ltConfig   = LEAVE_TYPE_CONFIG[form.leave_type];
  const balance    = balanceMap[form.leave_type];
  const policy     = policyMap[form.leave_type];
  const isCurrentTypeAvailable = !policies
    || Boolean(policy?.is_active && policy.matches_gender_for_requester);
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

  useEffect(() => {
    if (!policies || availableLeaveTypes.length === 0) return;
    if (availableLeaveTypes.some(type => type.key === form.leave_type)) return;
    setForm(previous => ({ ...previous, leave_type: availableLeaveTypes[0].key }));
    setDocFile(null);
  }, [availableLeaveTypes, form.leave_type, policies]);

  function setField<K extends keyof LeaveForm>(key: K, val: LeaveForm[K]) {
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });
    setForm(prev => ({ ...prev, [key]: val }));
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!isCurrentTypeAvailable)                    e.leave_type = "This leave type is not available for your profile.";
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

  const requestedLabel = preview ? preview.actual_leave_days : workDays;
  const balancePreviewText = ltConfig.isLwp
    ? "Unpaid — no balance deducted"
    : `${available} day${available === 1 ? "" : "s"} available · ${requestedLabel} day${requestedLabel === 1 ? "" : "s"} requested`;

  return (
    <div className="p-6">
      <div className="grid grid-cols-1 gap-x-5 gap-y-5 sm:grid-cols-2">
        <div>
          <SmallLbl text="Leave type" />
          <select
            className="field-input field-select"
            value={form.leave_type}
            onChange={event => setField("leave_type", event.target.value as LeaveForm["leave_type"])}
          >
            {availableLeaveTypes.map(type => <option key={type.key} value={type.key}>{type.label}</option>)}
          </select>
          <Err msg={errors.leave_type} />
          {policies && availableLeaveTypes.length === 0 && (
            <p className="mt-1.5 text-xs text-[var(--on-variant)]">No active leave types are available for your profile. Contact HR.</p>
          )}
          {policy?.policy_note && (
            <p className="mt-1.5 flex items-start gap-1.5 text-xs text-[var(--on-variant)]">
              <i className="ti ti-info-circle mt-px flex-shrink-0" /> {policy.policy_note}
            </p>
          )}
        </div>

        <div>
          <SmallLbl text="Duration" />
          <select
            className="field-input field-select"
            value={form.duration}
            onChange={event => handleDurationChange(event.target.value as DurationKey)}
          >
            {DURATION_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </div>

        <div>
          <SmallLbl text={isHalfDay ? "Date" : "From"} />
          <DateInput value={form.from_date} onChange={isoDate => setField("from_date", isoDate)} className={`field-input${errors.from_date ? " field-error" : ""}`} />
          <Err msg={errors.from_date} />
        </div>

        {!isHalfDay && (
          <div>
            <SmallLbl text="To" />
            <DateInput value={form.to_date} min={form.from_date} onChange={isoDate => setField("to_date", isoDate)} className={`field-input${errors.to_date ? " field-error" : ""}`} />
            <Err msg={errors.to_date} />
          </div>
        )}

        <div>
          <SmallLbl text="Reason" />
          <textarea
            className={`field-input${errors.reason ? " field-error" : ""}`}
            value={form.reason}
            onChange={event => setField("reason", event.target.value)}
            placeholder="Reason for leave"
            rows={3}
            maxLength={500}
            style={{ resize: "none" }}
          />
          <Err msg={errors.reason} />
        </div>

        <div>
          <SmallLbl text="Balance preview" />
          <div className="field-input flex items-center" style={{ background: "var(--bg-low)", color: "var(--on-variant)", minHeight: 76 }}>
            {previewLoading && canPreview ? "Checking balance…" : balancePreviewText}
          </div>
          {insufficientBalance && <Err msg="Insufficient leave balance for the selected dates." />}
        </div>
      </div>

      <LeaveSupportingDocument file={docFile} isRequired={ltConfig.requiresDoc} error={errors.doc} onChange={setDocFile} />

      <LeaveHandoverFields form={form} onChange={setField} />

      <div className="mt-6 flex items-center justify-between gap-2.5 border-t border-[var(--outline-v)] pt-4">
        <p className="text-xs text-[var(--on-variant)]">Submissions are routed for approval and retained in My Requests.</p>
        <div className="flex items-center gap-2.5">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={submitting}>Cancel</button>
        <button type="button" className="btn btn-filled" onClick={handleSubmit} disabled={submitting || insufficientBalance || !isCurrentTypeAvailable || availableLeaveTypes.length === 0}>
          {submitting ? <><i className="ti ti-loader-2 spin" /> Submitting…</> : "Submit request"}
        </button>
        </div>
      </div>
    </div>
  );
}
