"use client";

import { useState } from "react";
import { EMP_DATA, grossEarnings, totalDeductions, fmt, type PayrollEmployee } from "./payrollData";
import { EARNING_COMPONENTS, DEDUCTION_COMPONENTS, type SalaryComponent } from "./payrollConfig";

interface Props { onNext: () => void; onBack: () => void; }

type EditMode = "earnings" | "deductions";

interface EditState {
  idx: number;
  mode: EditMode;
  draft: Partial<PayrollEmployee>;
  selectedKey: keyof PayrollEmployee;
}

function Avatar({ text, color = "var(--primary)" }: { text: string; color?: string }) {
  return (
    <div style={{ width: 28, height: 28, borderRadius: "50%", background: color, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>
      {text}
    </div>
  );
}

function EmpCell({ e }: { e: PayrollEmployee }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <Avatar text={e.avatar} />
      <div>
        <div style={{ fontWeight: 600, fontSize: 13 }}>{e.name}</div>
        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{e.dept}</div>
      </div>
    </div>
  );
}

function RulesTable({
  rows, components, totalFn, totalColor, onEdit, mode,
}: {
  rows: PayrollEmployee[];
  components: SalaryComponent[];
  totalFn: (e: PayrollEmployee) => number;
  totalColor: string;
  onEdit: (idx: number, mode: EditMode) => void;
  mode: EditMode;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Employee</th>
            {components.map(c => (
              <th key={c.key as string} style={{ textAlign: "right" }}>{c.label}</th>
            ))}
            <th style={{ textAlign: "right", color: totalColor }}>
              {mode === "earnings" ? "Gross" : "Total Ded."}
            </th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((e, idx) => (
            <tr key={e.id}>
              <td><EmpCell e={e} /></td>
              {components.map(c => (
                <td key={c.key as string} style={{ textAlign: "right" }}>
                  {(e[c.key] as number) > 0
                    ? <span style={{ color: mode === "deductions" && !c.statutory ? "var(--error)" : undefined }}>{fmt(e[c.key] as number)}</span>
                    : "—"}
                </td>
              ))}
              <td style={{ textAlign: "right", fontWeight: 700, color: totalColor }}>
                {fmt(totalFn(e))}
              </td>
              <td>
                <button className="btn btn-ghost btn-sm" onClick={() => onEdit(idx, mode)}>
                  <i className="ti ti-edit" />
                </button>
              </td>
            </tr>
          ))}
          <tr style={{ background: "var(--bg-low)" }}>
            <td style={{ fontWeight: 700 }}>Total</td>
            {components.map(c => (
              <td key={c.key as string} style={{ textAlign: "right", fontWeight: 600 }}>
                {fmt(rows.reduce((s, e) => s + (e[c.key] as number), 0))}
              </td>
            ))}
            <td style={{ textAlign: "right", fontWeight: 700, color: totalColor }}>
              {fmt(rows.reduce((s, e) => s + totalFn(e), 0))}
            </td>
            <td />
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export default function EarningsDeductionsStep({ onNext, onBack }: Props) {
  const [rows, setRows] = useState<PayrollEmployee[]>(EMP_DATA.map(e => ({ ...e })));
  const [edit, setEdit] = useState<EditState | null>(null);

  function openEdit(idx: number, mode: EditMode) {
    const components = mode === "earnings" ? EARNING_COMPONENTS : DEDUCTION_COMPONENTS;
    setEdit({ idx, mode, draft: { ...rows[idx] }, selectedKey: components[0].key });
  }

  function saveEdit() {
    if (!edit) return;
    setRows(prev => prev.map((r, i) => i === edit.idx ? { ...r, ...edit.draft } as PayrollEmployee : r));
    setEdit(null);
  }

  const modalComponents = edit?.mode === "earnings" ? EARNING_COMPONENTS : DEDUCTION_COMPONENTS;
  const selected = modalComponents.find(c => c.key === edit?.selectedKey);
  const currentVal = edit ? (rows[edit.idx][edit.selectedKey] as number) : 0;
  const draftVal   = edit ? ((edit.draft[edit.selectedKey] as number) ?? 0) : 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* ── Earnings ── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-cash" /> Earnings Review</div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <span style={{ fontSize: 11, color: "var(--on-variant)", background: "var(--bg-low)", padding: "2px 8px", borderRadius: 4 }}>
              <i className="ti ti-settings" style={{ fontSize: 11 }} /> {EARNING_COMPONENTS.length} components from Payroll Settings
            </span>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Gross Total: <strong style={{ color: "var(--success)" }}>{fmt(rows.reduce((s, e) => s + grossEarnings(e), 0))}</strong>
            </span>
          </div>
        </div>
        <RulesTable rows={rows} components={EARNING_COMPONENTS} totalFn={grossEarnings} totalColor="var(--success)" onEdit={openEdit} mode="earnings" />
      </div>

      {/* ── Deductions ── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-minus-vertical" /> Deductions Review</div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <span style={{ fontSize: 11, color: "var(--on-variant)", background: "var(--bg-low)", padding: "2px 8px", borderRadius: 4 }}>
              <i className="ti ti-settings" style={{ fontSize: 11 }} /> {DEDUCTION_COMPONENTS.length} rules from Payroll Settings
            </span>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Total Deductions: <strong style={{ color: "var(--error)" }}>{fmt(rows.reduce((s, e) => s + totalDeductions(e), 0))}</strong>
            </span>
          </div>
        </div>
        <RulesTable rows={rows} components={DEDUCTION_COMPONENTS} totalFn={totalDeductions} totalColor="var(--error)" onEdit={openEdit} mode="deductions" />
        <div style={{ padding: "14px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
          <button className="btn btn-filled" onClick={onNext}>Continue <i className="ti ti-arrow-right" /></button>
        </div>
      </div>

      {/* ── Edit modal with component dropdown ── */}
      {edit && (
        <div className="modal-overlay open" onClick={() => setEdit(null)}>
          <div className="modal" style={{ maxWidth: 460 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <i className={`ti ${edit.mode === "earnings" ? "ti-cash" : "ti-minus-vertical"}`} style={{ marginRight: 8 }} />
                Edit {edit.mode === "earnings" ? "Earnings" : "Deductions"} — {rows[edit.idx].name}
              </div>
              <button className="modal-close" onClick={() => setEdit(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">

              {/* Component dropdown — options fetched from Payroll Settings config */}
              <div className="field-group mb-16">
                <label className="field-label">
                  <i className="ti ti-settings" style={{ fontSize: 11, marginRight: 4 }} />
                  Select Component <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(from Payroll Settings)</span>
                </label>
                <select
                  className="field-input field-select"
                  value={edit.selectedKey as string}
                  onChange={ev => setEdit(p => p ? { ...p, selectedKey: ev.target.value as keyof PayrollEmployee } : p)}
                >
                  {modalComponents.map(c => (
                    <option key={c.key as string} value={c.key as string}>
                      {c.label}{c.statutory ? " ★" : ""}
                    </option>
                  ))}
                </select>
                {selected && (
                  <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
                    Basis: {selected.basis}{selected.statutory ? " · Statutory" : ""}
                  </p>
                )}
              </div>

              {/* Current → New value */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <div className="field-group">
                  <label className="field-label">Current Value</label>
                  <div className="field-input" style={{ background: "var(--bg-low)", color: "var(--on-variant)", cursor: "default" }}>
                    {fmt(currentVal)}
                  </div>
                </div>
                <div className="field-group">
                  <label className="field-label">Override Value (₹)</label>
                  <input
                    type="number"
                    className="field-input"
                    min={0}
                    value={draftVal}
                    onChange={ev => setEdit(p => p ? { ...p, draft: { ...p.draft, [p.selectedKey]: Number(ev.target.value) } } : p)}
                  />
                </div>
              </div>

              {/* All-fields quick overview */}
              <div style={{ marginTop: 16, padding: "10px 14px", background: "var(--bg-low)", borderRadius: "var(--radius)", fontSize: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--on-variant)", textTransform: "uppercase", fontSize: 11, letterSpacing: "0.04em" }}>
                  All {edit.mode === "earnings" ? "Earning" : "Deduction"} Components
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 16px" }}>
                  {modalComponents.map(c => {
                    const val = (edit.draft[c.key] as number) ?? (rows[edit.idx][c.key] as number);
                    const isSelected = c.key === edit.selectedKey;
                    return (
                      <div
                        key={c.key as string}
                        style={{ display: "flex", justifyContent: "space-between", padding: "3px 6px", borderRadius: 4, background: isSelected ? "rgba(30,78,140,0.08)" : "transparent", cursor: "pointer" }}
                        onClick={() => setEdit(p => p ? { ...p, selectedKey: c.key } : p)}
                      >
                        <span style={{ color: isSelected ? "var(--primary)" : "var(--on-variant)", fontWeight: isSelected ? 600 : 400 }}>{c.label}</span>
                        <span style={{ fontWeight: 600 }}>{val > 0 ? fmt(val) : "—"}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setEdit(null)}>Cancel</button>
              <button className="btn btn-filled" onClick={saveEdit}>
                <i className="ti ti-check" /> Apply Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
