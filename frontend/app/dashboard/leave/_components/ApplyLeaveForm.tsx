"use client";

import { useState, useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { useFiscalYearConfig } from "@/lib/fiscalYear";
import {
  LeaveBalance, LeavePolicy, LeavePreview, LeaveRequest,
  LeaveTypeKey, DurationKey,
  LEAVE_TYPES_LIST, LEAVE_TYPE_CONFIG,
  calcWorkingDays, fmtDate,
} from "../_data";

interface LeaveForm {
  leave_type:          LeaveTypeKey;
  duration:            DurationKey;
  from_date:           string;
  to_date:             string;
  reason:              string;
  contact_during_leave: string;
  handover_to:         string;
  handover_notes:      string;
}

const BLANK: LeaveForm = {
  leave_type: "casual", duration: "full_day",
  from_date: "", to_date: "", reason: "",
  contact_during_leave: "", handover_to: "", handover_notes: "",
};

function Lbl({ text, required }: { text: string; required?: boolean }) {
  return (
    <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">
      {text}{required && <span className="text-red-500 ml-0.5 normal-case">*</span>}
    </label>
  );
}

function Err({ msg }: { msg?: string }) {
  if (!msg) return null;
  return (
    <p className="text-xs text-red-500 mt-1 flex items-center gap-1">
      <i className="ti ti-alert-circle text-xs" /> {msg}
    </p>
  );
}

function dayName(iso: string): string {
  if (!iso) return "";
  return new Date(iso + "T12:00:00").toLocaleDateString("en-US", { weekday: "short" });
}

export default function ApplyLeaveForm({ onCancel }: { onCancel: () => void }) {
  const { showToast } = useToast();
  const [form,          setForm]          = useState<LeaveForm>(BLANK);
  const [errors,        setErrors]        = useState<Record<string, string>>({});
  const [submitting,    setSubmitting]    = useState(false);
  const [submitted,     setSubmitted]     = useState<LeaveRequest | null>(null);
  const [docFile,       setDocFile]       = useState<File | null>(null);

  const { currentYear } = useFiscalYearConfig();
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

  const previewHolidays = preview?.company_holidays ?? [];
  const previewWeekOffs = preview?.week_offs ?? [];
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
      <div className="min-h-[60vh] flex items-center justify-center p-6">
        <div className="bg-white rounded-3xl border border-gray-200 shadow-lg p-10 text-center w-full max-w-md">
          <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-6">
            <i className="ti ti-circle-check text-4xl text-green-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-800 mb-2">Request Submitted!</h2>
          <p className="text-sm text-gray-500 mb-1">
            Your <strong className="text-blue-700">{ltConfig.label}</strong> request for{" "}
            <strong className="text-blue-700">{submitted.total_days} day{submitted.total_days !== 1 ? "s" : ""}</strong> has been sent for approval.
          </p>
          <p className="text-xs text-gray-400 mb-8">{fmtDate(submitted.start_date)} → {fmtDate(submitted.end_date)}</p>
          <div className="flex gap-3 justify-center">
            <button onClick={() => { setForm(BLANK); setDocFile(null); setSubmitted(null); }}
              className="px-5 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">
              Apply Another
            </button>
            <button onClick={onCancel}
              className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white"
              style={{ background: "#1e4e8c" }}>
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  const INPUT     = "w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm text-gray-800 bg-white outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100 placeholder:text-gray-400";
  const INPUT_ERR = "w-full border border-red-400 rounded-xl px-3.5 py-2.5 text-sm text-gray-800 bg-red-50 outline-none";

  return (
    <div className="flex flex-col gap-0">

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-gray-400 mb-4">
        <button onClick={onCancel} className="hover:text-gray-600">Leave Management</button>
        <i className="ti ti-chevron-right text-gray-300" />
        <span className="text-gray-700 font-medium">Apply for Leave</span>
      </div>

      <div className="flex gap-5 items-start">

        {/* ── Left column — form ───────────────────────────────────────────── */}
        <div className="flex-1 min-w-0 flex flex-col gap-4">

          {/* Leave type selector */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <Lbl text="Select Leave Type" required />
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-1">
              {LEAVE_TYPES_LIST.map(lt => {
                const selected = form.leave_type === lt.key;
                const bal      = balanceMap[lt.key];
                const avail    = bal ? Number(bal.available_days) : 0;
                const total    = bal ? Number(bal.total_days) : 0;
                const pct      = total > 0 ? Math.min(100, Math.round((avail / total) * 100)) : 0;
                return (
                  <button key={lt.key} onClick={() => setField("leave_type", lt.key)}
                    className={["relative text-left p-3.5 rounded-xl border-2 transition-all",
                      selected ? "shadow-md" : "border-gray-100 hover:border-gray-200 bg-gray-50 hover:bg-white"].join(" ")}
                    style={selected ? { borderColor: lt.color, background: lt.bg } : {}}>
                    {selected && (
                      <span className="absolute top-2.5 right-2.5 w-4 h-4 rounded-full flex items-center justify-center" style={{ background: lt.color }}>
                        <i className="ti ti-check text-white" style={{ fontSize: 9 }} />
                      </span>
                    )}
                    <div className="w-8 h-8 rounded-xl flex items-center justify-center mb-2.5" style={{ background: lt.bg }}>
                      <i className={`ti ${lt.icon} text-sm`} style={{ color: lt.color }} />
                    </div>
                    <div className="text-xs font-bold text-gray-800 mb-0.5">{lt.label}</div>
                    {lt.isLwp ? (
                      <div className="text-xs text-gray-400">Unpaid · Unlimited</div>
                    ) : (
                      <>
                        <div className="text-xs font-semibold mb-1.5" style={{ color: lt.color }}>{avail}d left</div>
                        <div className="h-1.5 rounded-full bg-gray-200 overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: lt.color }} />
                        </div>
                        {/* Only worth surfacing once something has actually been carried forward. */}
                        {bal && bal.carried_forward > 0 && (
                          <div className="text-[10px] text-gray-400 mt-1">
                            {bal.carry_forward_expiry_date ? `Expires ${fmtDate(bal.carry_forward_expiry_date)}` : "No expiry"}
                          </div>
                        )}
                      </>
                    )}
                  </button>
                );
              })}
            </div>
            {policy?.policy_note && (
              <div className="mt-3 flex items-start gap-2 text-xs text-gray-500 bg-gray-50 rounded-xl px-3.5 py-2.5 border border-gray-100">
                <i className="ti ti-info-circle mt-0.5 flex-shrink-0" style={{ color: ltConfig.color }} />
                <span>{policy.policy_note}</span>
              </div>
            )}
          </div>

          {/* Duration + dates */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <div className="flex flex-col gap-5">
              <div>
                <Lbl text="Duration" />
                <div className="flex gap-2 flex-wrap">
                  {([
                    { val: "full_day"       as const, icon: "ti-sun",      label: "Full Day"            },
                    { val: "half_morning"   as const, icon: "ti-sun-high", label: "Half Day · Morning"  },
                    { val: "half_afternoon" as const, icon: "ti-sunset-2", label: "Half Day · Afternoon"},
                  ]).map(opt => (
                    <button key={opt.val}
                      onClick={() => { setField("duration", opt.val); if (opt.val !== "full_day") setField("to_date", ""); }}
                      className={["flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border-2 transition-all",
                        form.duration === opt.val ? "text-white border-blue-700" : "border-gray-200 text-gray-600 bg-gray-50 hover:bg-white"].join(" ")}
                      style={form.duration === opt.val ? { background: "#1e4e8c" } : {}}>
                      <i className={`ti ${opt.icon} text-sm`} />
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Lbl text="Start Date" required />
                  <div className="relative">
                    <i className="ti ti-calendar absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm pointer-events-none" />
                    <input type="date" value={form.from_date} onChange={e => setField("from_date", e.target.value)}
                      className={[(errors.from_date ? INPUT_ERR : INPUT), "pl-9"].join(" ")} />
                  </div>
                  {form.from_date && !errors.from_date && (
                    <p className="text-xs text-gray-400 mt-1">{dayName(form.from_date)}, {fmtDate(form.from_date)}</p>
                  )}
                  <Err msg={errors.from_date} />
                </div>
                <div>
                  <Lbl text="End Date" required={!isHalfDay} />
                  <div className="relative">
                    <i className="ti ti-calendar absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm pointer-events-none" />
                    <input type="date"
                      value={isHalfDay ? form.from_date : form.to_date}
                      min={form.from_date}
                      disabled={isHalfDay}
                      onChange={e => setField("to_date", e.target.value)}
                      className={[(errors.to_date ? INPUT_ERR : INPUT), "pl-9", isHalfDay ? "opacity-40 cursor-not-allowed" : ""].join(" ")} />
                  </div>
                  <Err msg={errors.to_date} />
                </div>
              </div>

              {/* Instant client-side estimate — shown only until the authoritative
                  server preview below arrives, so the two never disagree on screen. */}
              {!preview && workDays > 0 && (
                <div className={["flex items-center justify-between gap-3 rounded-xl px-4 py-3 border",
                  overLimit ? "bg-red-50 border-red-200" : "border-blue-100"].join(" ")}
                  style={overLimit ? {} : { background: "rgba(30,78,140,0.05)" }}>
                  <div className="flex items-center gap-2">
                    <i className={`ti ${overLimit ? "ti-alert-triangle text-red-500" : "ti-calendar-check"} text-sm`}
                      style={!overLimit ? { color: "#1e4e8c" } : {}} />
                    <span className={`text-sm font-bold ${overLimit ? "text-red-600" : "text-blue-800"}`}>
                      {workDays} working day{workDays !== 1 ? "s" : ""}
                    </span>
                  </div>
                  {!ltConfig.isLwp && overLimit && (
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-red-100 text-red-700">
                      Exceeds balance by {workDays - available}d
                    </span>
                  )}
                </div>
              )}

              {previewLoading && canPreview && (
                <div className="flex items-center gap-1.5 text-xs text-gray-400">
                  <i className="ti ti-loader-2 animate-spin" /> Checking balance and holidays…
                </div>
              )}

              {preview && (
                <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3.5 flex flex-col gap-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className={["text-sm font-bold", preview.lop_days > 0 ? "text-amber-700" : "text-blue-800"].join(" ")}>
                      {preview.actual_leave_days} working day{preview.actual_leave_days !== 1 ? "s" : ""}
                    </span>
                    {preview.lop_days > 0 && (
                      <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-100 text-amber-700">
                        {preview.lop_days}d will be LOP
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-y-1.5 text-sm border-t border-gray-200 pt-3">
                    <span className="text-gray-500">Calendar Days</span>
                    <span className="font-semibold text-gray-800 text-right">{preview.calendar_days}</span>
                    <span className="text-gray-500">Actual Leave Days</span>
                    <span className="font-semibold text-gray-800 text-right">{preview.actual_leave_days}</span>
                    <span className="text-gray-500">Available Balance</span>
                    <span className="font-semibold text-gray-800 text-right">{preview.available_balance}</span>
                    <span className="text-gray-500">Earned Leave Used</span>
                    <span className="font-semibold text-gray-800 text-right">{preview.earned_leave_used}</span>
                    <span className="text-gray-500">LOP Days</span>
                    <span className={["font-semibold text-right", preview.lop_days > 0 ? "text-amber-700" : "text-gray-800"].join(" ")}>
                      {preview.lop_days}
                    </span>
                  </div>

                  {previewHolidays.length > 0 && (
                    <div className="border-t border-gray-200 pt-2.5">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Company Holidays</p>
                      <div className="flex flex-col gap-1">
                        {previewHolidays.map(h => (
                          <div key={`${h.date}-${h.name}`} className="flex items-center justify-between text-xs text-gray-600">
                            <span>{h.name}</span>
                            {/* Backend sends a pre-formatted display string (e.g. "15 Aug"),
                                not an ISO date — render as-is, do not pass through fmtDate. */}
                            <span className="text-gray-400">{h.date}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {previewWeekOffs.length > 0 && (
                    <div className="border-t border-gray-200 pt-2.5">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Week-Offs</p>
                      <div className="flex flex-wrap gap-1.5">
                        {previewWeekOffs.map(w => (
                          <span key={w.date} className="text-xs text-gray-600 bg-white border border-gray-200 rounded-full px-2.5 py-0.5">
                            {fmtDate(w.date)} · {w.day}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {preview?.warning && (
                <div className="flex items-start gap-2 text-xs text-blue-800 bg-blue-50 border border-blue-200 rounded-lg px-3.5 py-2.5">
                  <i className="ti ti-info-circle mt-0.5 flex-shrink-0" />
                  <span>{preview.warning}</span>
                </div>
              )}

              {insufficientBalance && (
                <div className="flex items-start gap-2 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3.5 py-2.5">
                  <i className="ti ti-alert-triangle mt-0.5 flex-shrink-0" />
                  <span>Insufficient leave balance for the selected dates. This request cannot be submitted.</span>
                </div>
              )}
            </div>
          </div>

          {/* Reason + Document */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 flex flex-col gap-5">
            <div>
              <Lbl text="Reason for Leave" required />
              <textarea value={form.reason} onChange={e => setField("reason", e.target.value)}
                placeholder="Briefly describe the reason for your leave request…"
                rows={4} maxLength={500}
                className={[(errors.reason ? INPUT_ERR : INPUT), "resize-none"].join(" ")} />
              <div className="flex justify-between mt-1">
                <Err msg={errors.reason} />
                <span className={`text-xs ml-auto ${form.reason.length > 450 ? "text-amber-500" : "text-gray-400"}`}>
                  {form.reason.length}/500
                </span>
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <Lbl text="Supporting Document" />
                {ltConfig.requiresDoc
                  ? <span className="text-xs font-semibold text-red-500 -mt-1.5">(Required)</span>
                  : <span className="text-xs text-gray-400 -mt-1.5">(Optional)</span>}
              </div>
              {docFile ? (
                <div className="flex items-center gap-3 p-3.5 bg-green-50 border border-green-200 rounded-xl">
                  <i className="ti ti-file-check text-green-600 text-lg" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-green-800 truncate">{docFile.name}</p>
                    <p className="text-xs text-green-600">Attached successfully</p>
                  </div>
                  <button onClick={() => setDocFile(null)} className="text-gray-400 hover:text-red-500">
                    <i className="ti ti-x" />
                  </button>
                </div>
              ) : (
                <label className={["flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-2xl py-7 px-4 cursor-pointer transition-all",
                  errors.doc ? "border-red-300 bg-red-50" : "border-gray-200 bg-gray-50 hover:border-blue-400 hover:bg-blue-50"].join(" ")}>
                  <i className="ti ti-cloud-upload text-gray-400 text-2xl" />
                  <div className="text-center">
                    <p className="text-sm font-medium text-gray-700">Click to upload or drag & drop</p>
                    <p className="text-xs text-gray-400 mt-0.5">PDF, JPG, PNG · Max 5 MB</p>
                  </div>
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden"
                    onChange={e => { const f = e.target.files?.[0]; if (f) setDocFile(f); }} />
                </label>
              )}
              <Err msg={errors.doc} />
            </div>
          </div>

          {/* Handover */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 flex flex-col gap-4">
            <div className="flex items-center gap-2 mb-1">
              <i className="ti ti-arrow-forward text-sm" style={{ color: "#1e4e8c" }} />
              <span className="text-sm font-semibold text-gray-700">Handover & Contact</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Lbl text="Handover To" />
                <input type="text" value={form.handover_to} onChange={e => setField("handover_to", e.target.value)}
                  placeholder="Colleague name" className={INPUT} />
              </div>
              <div>
                <Lbl text="Emergency Contact" />
                <input type="text" value={form.contact_during_leave} onChange={e => setField("contact_during_leave", e.target.value)}
                  placeholder="+91 9876543210" className={INPUT} />
              </div>
            </div>
            <div>
              <Lbl text="Handover Notes" />
              <textarea value={form.handover_notes} onChange={e => setField("handover_notes", e.target.value)}
                placeholder="Pending tasks, important context…" rows={2} maxLength={300}
                className={[INPUT, "resize-none"].join(" ")} />
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between gap-3 flex-wrap py-2">
            <button onClick={onCancel}
              className="px-5 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">
              Cancel
            </button>
            <button onClick={handleSubmit} disabled={submitting || insufficientBalance}
              className="flex items-center gap-2 px-7 py-2.5 rounded-xl text-sm font-semibold text-white shadow-md"
              style={{ background: submitting || insufficientBalance ? "#7fa3c8" : "#1e4e8c", cursor: submitting || insufficientBalance ? "not-allowed" : "pointer" }}>
              {submitting
                ? <><i className="ti ti-loader-2" /> Submitting…</>
                : <><i className="ti ti-send" /> Submit Request</>}
            </button>
          </div>
        </div>

        {/* ── Right sidebar ────────────────────────────────────────────────────── */}
        <div className="w-72 flex-shrink-0 flex flex-col gap-4 sticky top-4">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-3">Leave Balance</p>
            <div className="flex items-center gap-2 mb-2.5">
              <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: ltConfig.bg }}>
                <i className={`ti ${ltConfig.icon} text-sm`} style={{ color: ltConfig.color }} />
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-700">{ltConfig.label}</p>
                {ltConfig.isLwp
                  ? <p className="text-xs text-gray-400">Unpaid · No limit</p>
                  : <p className="text-xs text-gray-400">{available} of {balance ? Number(balance.total_days) : 0} days left</p>
                }
              </div>
            </div>
            {!ltConfig.isLwp && balance && (
              <>
                <div className="h-2 rounded-full bg-gray-100 overflow-hidden mb-1.5">
                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.round((available / Number(balance.total_days)) * 100))}%`, background: ltConfig.color }} />
                </div>
                <div className="flex justify-between text-xs text-gray-400">
                  <span>{Number(balance.used_days)} used</span>
                  <span>{available} remaining</span>
                </div>
              </>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
