"use client";

// Optional handover and emergency-contact details — collapsed by default so the form
// stays short for the common case.

import { Lbl, type LeaveForm } from "./applyLeaveFormHelpers";

interface Props {
  form: LeaveForm;
  onChange: <K extends keyof LeaveForm>(key: K, value: LeaveForm[K]) => void;
}

export default function LeaveHandoverFields({ form, onChange }: Props) {
  const hasContent = !!(form.handover_to || form.contact_during_leave || form.handover_notes);
  return (
    <details className="group rounded-lg border border-[var(--outline-v)]" open={hasContent}>
      <summary className="flex cursor-pointer list-none items-center justify-between px-3.5 py-2.5 text-[13px] font-semibold text-[var(--on-bg)]">
        <span>Handover &amp; contact <span className="ml-1 text-xs font-normal text-[var(--on-variant)]">Optional</span></span>
        <i className="ti ti-chevron-down text-[var(--on-variant)] transition-transform group-open:rotate-180" />
      </summary>
      <div className="flex flex-col gap-4 border-t border-[var(--outline-v)] px-3.5 py-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Lbl text="Handover to" />
            <input className="field-input" value={form.handover_to} onChange={event => onChange("handover_to", event.target.value)} placeholder="Colleague name" />
          </div>
          <div>
            <Lbl text="Contact during leave" />
            <input className="field-input" value={form.contact_during_leave} onChange={event => onChange("contact_during_leave", event.target.value)} placeholder="+91 98765 43210" />
          </div>
        </div>
        <div>
          <Lbl text="Handover notes" />
          <textarea className="field-input" rows={2} maxLength={300} value={form.handover_notes} onChange={event => onChange("handover_notes", event.target.value)} placeholder="Pending tasks and important context" style={{ resize: "none" }} />
        </div>
      </div>
    </details>
  );
}
