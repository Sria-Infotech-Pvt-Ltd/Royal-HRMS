"use client";

// The "Add OT entry" card: who worked the overtime and when, which kind it was (clickable cards showing the rate), the hours with a live
// duration, who approved it and why. The same fields, rules and wording as before, laid out so each step is clear.

import { useT } from "@/hooks/useI18n";
import SearchableSelect from "@/components/SearchableSelect";
import type { OvertimeCreatePayload } from "@/types/attendance";
import AttendanceDatePicker from "./AttendanceDatePicker";
import { PALETTE, tint } from "./attendancePalette";
import { OT_TYPES, durationLabel, minutesBetween } from "./otEntry";

export interface PickerEmployee { employee_id: string; full_name: string }

interface Props {
  form: OvertimeCreatePayload;
  onField: <K extends keyof OvertimeCreatePayload>(key: K, value: OvertimeCreatePayload[K]) => void;
  employees: PickerEmployee[];
  approvers: PickerEmployee[];
  todayISO: string;
  error: string | null;
  canCreate: boolean;
  submitting: boolean;
  onSubmit: () => void;
  onReset: () => void;
}

const initialsOf = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0].toUpperCase()).join("") || "?";

function Step({ number, title, children }: { number: number; title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <span aria-hidden="true" style={{ width: 22, height: 22, borderRadius: "50%", display: "grid", placeItems: "center", fontSize: 11.5, fontWeight: 800, background: tint(PALETTE.brand, 0.14), color: PALETTE.brand }}>{number}</span>
        <span style={{ fontSize: 13.5, fontWeight: 700, color: "var(--on-bg)" }}>{title}</span>
      </div>
      {children}
    </div>
  );
}

export default function OtEntryForm({ form, onField, employees, approvers, todayISO, error, canCreate, submitting, onSubmit, onReset }: Props) {
  const t = useT();
  const minutes = minutesBetween(form.ot_start, form.ot_end);
  const chosen = employees.find(employee => employee.employee_id === form.employee_id);
  return (
    <section aria-label={t("Add OT entry")} className="card" style={{ padding: 0, overflow: "hidden" }}>
      <header style={{ padding: "16px 20px", display: "flex", alignItems: "center", gap: 12, borderBottom: "1px solid var(--outline-v)", background: `linear-gradient(135deg, ${tint(PALETTE.brand, 0.09)} 0%, var(--surface) 60%)` }}>
        <span aria-hidden="true" style={{ width: 40, height: 40, borderRadius: 12, display: "grid", placeItems: "center", background: PALETTE.brand, color: "#fff", fontSize: 20, boxShadow: `0 4px 12px ${tint(PALETTE.brand, 0.35)}` }}><i className="ti ti-clock-plus" /></span>
        <div>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "var(--on-bg)" }}>{t("Add OT Entry")}</h3>
          <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "var(--on-variant)" }}>{t("Record overtime an employee worked. It is paid at the rate of the type you pick.")}</p>
        </div>
      </header>

      <div style={{ padding: "20px 22px 18px" }}>
        {error && <div className="alert alert-error mb-16" role="alert"><i className="ti ti-alert-circle" /> <span>{error}</span></div>}

        <Step number={1} title={t("Who worked, and on which day?")}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16, alignItems: "start" }}>
            <div>
              <label className="field-label" style={{ display: "block", marginBottom: 6 }}>{t("Employee")}</label>
              <SearchableSelect
                value={form.employee_id} onChange={value => onField("employee_id", value)} placeholder={t("Select employee…")} searchPlaceholder={t("Search by name or ID…")}
                options={employees.map(employee => ({ value: employee.employee_id, label: `${employee.full_name} (${employee.employee_id})` }))} inputClassName="field-input"
              />
              {chosen && (
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10, padding: "8px 12px", borderRadius: 12, background: tint(PALETTE.brand, 0.07), border: `1px solid ${tint(PALETTE.brand, 0.18)}` }}>
                  <span aria-hidden="true" style={{ width: 30, height: 30, borderRadius: "50%", display: "grid", placeItems: "center", fontSize: 11, fontWeight: 800, color: "#fff", background: `linear-gradient(135deg, ${PALETTE.brand}, #A78BFA)` }}>{initialsOf(chosen.full_name)}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{chosen.full_name} <span style={{ color: "var(--on-variant)", fontWeight: 500 }}>· {chosen.employee_id}</span></span>
                </div>
              )}
            </div>
            <div>
              <label className="field-label" style={{ display: "block", marginBottom: 6 }}>{t("Date")}</label>
              <AttendanceDatePicker date={form.date} todayISO={todayISO} allowFuture onChange={isoDate => onField("date", isoDate)} />
            </div>
          </div>
        </Step>

        <Step number={2} title={t("What kind of overtime was it?")}>
          <div role="radiogroup" aria-label={t("OT type")} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 10 }}>
            {OT_TYPES.map(type => {
              const selected = form.ot_type === type.value;
              return (
                <button
                  key={type.value} type="button" role="radio" aria-checked={selected} onClick={() => onField("ot_type", type.value)}
                  style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", textAlign: "left", cursor: "pointer", borderRadius: 14, transition: "all .15s ease", background: selected ? tint(type.colour, 0.1) : "var(--surface)", border: `1.5px solid ${selected ? type.colour : "var(--outline-v)"}`, boxShadow: selected ? `0 0 0 3px ${tint(type.colour, 0.15)}` : "none" }}
                >
                  <span aria-hidden="true" style={{ width: 36, height: 36, borderRadius: 10, display: "grid", placeItems: "center", fontSize: 18, background: selected ? type.colour : tint(type.colour, 0.14), color: selected ? "#fff" : type.colour }}><i className={`ti ${type.icon}`} /></span>
                  <span style={{ flex: 1 }}>
                    <span style={{ display: "flex", alignItems: "baseline", gap: 6, fontWeight: 700, fontSize: 14, color: "var(--on-bg)" }}>{t(type.label)}<span style={{ fontSize: 12, fontWeight: 800, color: type.colour }}>{type.multiplier}</span></span>
                    <span style={{ display: "block", fontSize: 11.5, color: "var(--on-variant)", marginTop: 1 }}>{t(type.hint)}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </Step>

        <Step number={3} title={t("How long?")}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 140px" }}>
              <label className="field-label" htmlFor="ot-start" style={{ display: "block", marginBottom: 6 }}>{t("OT Start")}</label>
              <input id="ot-start" type="time" className="field-input" value={form.ot_start} onChange={event => onField("ot_start", event.target.value)} />
            </div>
            <div style={{ flex: "1 1 140px" }}>
              <label className="field-label" htmlFor="ot-end" style={{ display: "block", marginBottom: 6 }}>{t("OT End")}</label>
              <input id="ot-end" type="time" className="field-input" value={form.ot_end} onChange={event => onField("ot_end", event.target.value)} />
            </div>
            <div role="status" aria-label={t("Overtime duration")} style={{ flex: "1 1 160px", display: "flex", alignItems: "center", gap: 8, height: 40, padding: "0 14px", borderRadius: 12, fontWeight: 700, fontSize: 13.5, background: tint(minutes === null ? PALETTE.absent : PALETTE.present, 0.1), color: minutes === null ? PALETTE.absent : PALETTE.present, border: `1px solid ${tint(minutes === null ? PALETTE.absent : PALETTE.present, 0.3)}` }}>
              <i className={`ti ${minutes === null ? "ti-alert-triangle" : "ti-hourglass-high"}`} aria-hidden="true" />
              {minutes === null ? t("End must be after start") : t("{duration} of overtime", { duration: durationLabel(minutes) })}
            </div>
          </div>
        </Step>

        <Step number={4} title={t("Who approved it, and why?")}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
            <div>
              <label className="field-label" style={{ display: "block", marginBottom: 6 }}>{t("Approved By")}</label>
              <SearchableSelect
                value={form.approved_by ?? ""} onChange={value => onField("approved_by", value)} placeholder={t("Select approver…")} searchPlaceholder={t("Search approvers…")}
                options={approvers.map(approver => ({ value: approver.employee_id, label: approver.full_name ?? approver.employee_id }))} inputClassName="field-input"
              />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label className="field-label" htmlFor="ot-reason" style={{ display: "block", marginBottom: 6 }}>{t("Reason / Work Done")}</label>
              <textarea id="ot-reason" className="field-input" style={{ minHeight: 76, width: "100%" }} placeholder={t("Describe the overtime work…")} value={form.reason ?? ""} onChange={event => onField("reason", event.target.value)} />
            </div>
          </div>
        </Step>

        {canCreate && (
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, paddingTop: 4 }}>
            <button className="btn btn-ghost" type="button" onClick={onReset} disabled={submitting}>{t("Reset")}</button>
            <button className="btn btn-filled" type="button" onClick={onSubmit} disabled={submitting} style={{ minWidth: 150 }}>
              {submitting ? <><i className="ti ti-loader-2 animate-spin" /> {t("Adding…")}</> : <><i className="ti ti-plus" /> {t("Add OT Entry")}</>}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
