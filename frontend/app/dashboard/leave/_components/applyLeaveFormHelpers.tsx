import { LeaveTypeKey, DurationKey } from "../_data";

export interface LeaveForm {
  leave_type:          LeaveTypeKey;
  duration:            DurationKey;
  from_date:           string;
  to_date:             string;
  reason:              string;
  contact_during_leave: string;
  handover_to:         string;
  handover_notes:      string;
}

export const BLANK: LeaveForm = {
  leave_type: "casual", duration: "full_day",
  from_date: "", to_date: "", reason: "",
  contact_during_leave: "", handover_to: "", handover_notes: "",
};

/** Label above a form control. */
export function Lbl({ text, required, hint }: { text: string; required?: boolean; hint?: string }) {
  return (
    <label className="mb-1.5 flex items-baseline gap-1.5 text-[13px] font-semibold text-[var(--on-bg)]">
      <span>{text}{required && <span className="ml-0.5 text-[var(--error)]">*</span>}</span>
      {hint && <span className="text-xs font-normal text-[var(--on-variant)]">{hint}</span>}
    </label>
  );
}

export function Err({ msg }: { msg?: string }) {
  if (!msg) return null;
  return (
    <p className="mt-1.5 flex items-center gap-1 text-xs text-[var(--error)]">
      <i className="ti ti-alert-circle text-xs" /> {msg}
    </p>
  );
}

export function dayName(iso: string): string {
  if (!iso) return "";
  return new Date(iso + "T12:00:00").toLocaleDateString("en-US", { weekday: "short" });
}
