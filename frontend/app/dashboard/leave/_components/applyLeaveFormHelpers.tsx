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

export function Lbl({ text, required }: { text: string; required?: boolean }) {
  return (
    <label className="block text-xs font-semibold text-[var(--on-variant)] mb-1.5 uppercase tracking-wide">
      {text}{required && <span className="text-[var(--error)] ml-0.5 normal-case">*</span>}
    </label>
  );
}

export function Err({ msg }: { msg?: string }) {
  if (!msg) return null;
  return (
    <p className="text-xs text-[var(--error)] mt-1 flex items-center gap-1">
      <i className="ti ti-alert-circle text-xs" /> {msg}
    </p>
  );
}

export function dayName(iso: string): string {
  if (!iso) return "";
  return new Date(iso + "T12:00:00").toLocaleDateString("en-US", { weekday: "short" });
}
