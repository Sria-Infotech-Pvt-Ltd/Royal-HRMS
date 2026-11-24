"use client";

// Small presentational pieces shared by the Add / Edit Company Code form sections: a section card, a labelled field, a choice card
// and the Active / Inactive switch. Styling uses the app's CSS variables only.

import type { ReactNode } from "react";
import { useT } from "@/hooks/useI18n";

interface FormSectionProps {
  id: string;
  /** A plain question or label, e.g. "Where is it?". */
  title: string;
  /** One plain sentence of help. */
  subtitle: string;
  children: ReactNode;
}

/** A group of fields with a heading and one line of help. No box, so the screen stays calm. */
export function FormSection({ id, title, subtitle, children }: FormSectionProps) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} style={{ paddingTop: 22, marginTop: 22, borderTop: "1px solid var(--outline-v)" }}>
      <h3 id={`${id}-title`} style={{ margin: 0, fontSize: 15, fontWeight: 700, color: "var(--on-bg)" }}>{title}</h3>
      <p style={{ margin: "3px 0 16px", fontSize: 12.5, color: "var(--on-variant)" }}>{subtitle}</p>
      {children}
    </section>
  );
}

interface CollapsibleSectionProps {
  id: string;
  icon: string;
  title: string;
  /** What is set right now, shown while folded: "Not assigned", "On: within 150 m of the office". */
  summary: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}

/** An optional part of the form, folded away until it is needed. Its one-line summary says what is set without opening it. */
export function CollapsibleSection({ id, icon, title, summary, open, onToggle, children }: CollapsibleSectionProps) {
  return (
    <section id={id} style={{ marginTop: 14, border: "1px solid var(--outline-v)", borderRadius: 12, background: open ? "var(--surface)" : "var(--bg-low)" }}>
      <button
        type="button" onClick={onToggle} aria-expanded={open} aria-controls={`${id}-panel`}
        style={{ display: "flex", alignItems: "center", gap: 12, width: "100%", padding: "13px 16px", background: "none", border: 0, cursor: "pointer", textAlign: "left" }}
      >
        <i className={`ti ${icon}`} aria-hidden="true" style={{ fontSize: 18, color: "var(--primary)" }} />
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ display: "block", fontSize: 14, fontWeight: 600, color: "var(--on-bg)" }}>{title}</span>
          <span style={{ display: "block", fontSize: 12, color: "var(--on-variant)", marginTop: 1 }}>{summary}</span>
        </span>
        <i className={`ti ${open ? "ti-chevron-up" : "ti-chevron-down"}`} aria-hidden="true" style={{ color: "var(--on-variant)" }} />
      </button>
      {open && <div id={`${id}-panel`} style={{ padding: "4px 16px 16px" }}>{children}</div>}
    </section>
  );
}

interface FieldProps { label: string; required?: boolean; hint?: ReactNode; error?: string; htmlFor?: string; children: ReactNode }

export function Field({ label, required, hint, error, htmlFor, children }: FieldProps) {
  return (
    <div className="field-group">
      <label className="field-label" htmlFor={htmlFor}>{label}{required && <span style={{ color: "var(--error)" }}> *</span>}</label>
      {children}
      {error ? <p className="field-error-msg">{error}</p> : hint ? <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>{hint}</div> : null}
    </div>
  );
}

interface ChoiceCardProps { checked: boolean; onChange: (checked: boolean) => void; icon: string; title: string; description: string }

/** A whole-card checkbox: easier to hit than a tiny box, and it says what ticking it does. */
export function ChoiceCard({ checked, onChange, icon, title, description }: ChoiceCardProps) {
  return (
    <label style={{
      display: "flex", gap: 10, alignItems: "flex-start", padding: "10px 12px", borderRadius: 12, cursor: "pointer",
      border: `1.5px solid ${checked ? "var(--primary)" : "var(--outline-v)"}`, background: checked ? "var(--primary-c, #f5f3ff)" : "var(--surface)",
    }}>
      <input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} style={{ marginTop: 3 }} />
      <span>
        <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
          <i className={`ti ${icon}`} aria-hidden="true" style={{ color: "var(--primary)" }} />{title}
        </span>
        <span style={{ display: "block", fontSize: 11.5, color: "var(--on-variant)", marginTop: 2 }}>{description}</span>
      </span>
    </label>
  );
}

const STATUSES = [{ value: "active", label: "Active", dot: "var(--success, #16a34a)" }, { value: "inactive", label: "Inactive", dot: "var(--outline, #9ca3af)" }];

export function StatusSwitch({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const t = useT();
  return (
    <div role="radiogroup" aria-label={t("Status")} style={{ display: "inline-flex", padding: 3, borderRadius: 999, background: "var(--bg-low)", border: "1px solid var(--outline-v)" }}>
      {STATUSES.map(status => {
        const selected = value === status.value;
        return (
          <button
            key={status.value} type="button" role="radio" aria-checked={selected} onClick={() => onChange(status.value)}
            style={{
              display: "flex", alignItems: "center", gap: 6, padding: "6px 16px", borderRadius: 999, border: 0, cursor: "pointer", fontSize: 13, fontWeight: 600,
              background: selected ? "var(--surface)" : "transparent", color: selected ? "var(--on-bg)" : "var(--on-variant)",
              boxShadow: selected ? "0 1px 3px rgba(0,0,0,.12)" : "none",
            }}
          >
            <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: "50%", background: status.dot }} />{t(status.label)}
          </button>
        );
      })}
    </div>
  );
}
