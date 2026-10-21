"use client";

// Assign CTC → the employee's own salary components. Edits here change only
// this employee's new revision — never the shared structure or anyone else.
// Amounts shown come from the server preview (same calculation as payroll).
//
// Three pieces, laid out as separate sections by SalarySetupTab:
//   default export      — the editable components table
//   SalarySummary       — monthly / annual totals and difference from CTC
//   RevisionComparison  — current vs proposed, collapsed by default

import type { CSSProperties } from "react";
import type { SalaryComponentInput, SalaryPreview, SalaryPreviewRow } from "@/types/payroll";
import { CALCULATION_LABEL, COMPONENT_TYPE_LABEL, ROLE_LABEL, blankComponent, compareRows } from "@/lib/salaryComponents";

// Small muted helper text under fields / tables.
const HELP: CSSProperties = { fontSize: 11.5, color: "var(--on-variant)", lineHeight: 1.4 };

const inr = (n: number | string | null) =>
  n === null ? "—" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

// Compact controls so every column fits and stays readable.
const CONTROL: CSSProperties = { padding: "7px 9px", fontSize: 12.5 };
const CELL: CSSProperties = { padding: "8px 8px" };
const NUM: CSSProperties = { ...CELL, textAlign: "right", whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" };

export default function SalaryComponentsEditor({
  rows, onChange, preview, disabled,
}: {
  rows: SalaryComponentInput[];
  onChange: (rows: SalaryComponentInput[]) => void;
  preview: SalaryPreview | null;
  disabled?: boolean;
}) {
  // Preview rows line up with the submitted rows by name (names are unique).
  const amounts = new Map<string, SalaryPreviewRow>((preview?.components ?? []).map(r => [r.name, r]));
  const set = (i: number, patch: Partial<SalaryComponentInput>) =>
    onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="table-wrap" style={{ border: "1px solid var(--outline-v)", borderRadius: "var(--radius)" }}>
        <table style={{ minWidth: 940, tableLayout: "fixed" }}>
          <colgroup>
            <col style={{ width: 44 }} />
            <col />
            <col style={{ width: 126 }} />
            <col style={{ width: 160 }} />
            <col style={{ width: 160 }} />
            <col style={{ width: 120 }} />
            <col style={{ width: 108 }} />
            <col style={{ width: 116 }} />
            <col style={{ width: 44 }} />
          </colgroup>
          <thead>
            <tr>
              <th style={CELL} title="Include in this revision">On</th>
              <th style={CELL}>Component</th>
              <th style={CELL}>Type</th>
              <th style={CELL}>Payslip line</th>
              <th style={CELL}>Method</th>
              <th style={CELL}>Value</th>
              <th style={{ ...CELL, textAlign: "right" }}>Monthly</th>
              <th style={{ ...CELL, textAlign: "right" }}>Annual</th>
              <th style={CELL}><span className="sr-only">Remove</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const calc = amounts.get(r.name.trim());
              const deduction = r.component_type === "deduction";
              const unit = r.calculation_type === "fixed" ? "₹" : "%";
              return (
                <tr key={i} style={{
                  opacity: r.is_enabled ? 1 : 0.55,
                  boxShadow: deduction ? "inset 3px 0 0 var(--error)" : undefined,
                }}>
                  <td style={{ ...CELL, textAlign: "center" }}>
                    <input type="checkbox" checked={r.is_enabled} disabled={disabled}
                      aria-label={`Include ${r.name || "component"}`}
                      onChange={e => set(i, { is_enabled: e.target.checked })} />
                  </td>
                  <td style={CELL}>
                    <input className="field-input" style={CONTROL} value={r.name} disabled={disabled} maxLength={100}
                      placeholder="Component name" aria-label="Component name"
                      onChange={e => set(i, { name: e.target.value })} />
                    {r.source_component === null && (
                      <span className="badge badge-info" style={{ marginTop: 4, fontSize: 10.5, padding: "1px 8px" }}>
                        This employee only
                      </span>
                    )}
                  </td>
                  <td style={CELL}>
                    <select className="field-input" style={CONTROL} value={r.component_type} disabled={disabled}
                      aria-label="Type"
                      onChange={e => set(i, { component_type: e.target.value as SalaryComponentInput["component_type"] })}>
                      {Object.entries(COMPONENT_TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </td>
                  <td style={CELL}>
                    <select className="field-input" style={CONTROL} value={r.role} disabled={disabled}
                      aria-label="Payslip line"
                      onChange={e => set(i, { role: e.target.value as SalaryComponentInput["role"] })}>
                      {Object.entries(ROLE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </td>
                  <td style={CELL}>
                    <select className="field-input" style={CONTROL} value={r.calculation_type} disabled={disabled}
                      aria-label="Calculation method"
                      onChange={e => set(i, { calculation_type: e.target.value as SalaryComponentInput["calculation_type"] })}>
                      {Object.entries(CALCULATION_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </td>
                  <td style={CELL}>
                    <div style={{ position: "relative" }}>
                      <input className="field-input" type="number" min={0} step="any" value={r.value} disabled={disabled}
                        aria-label={`Value (${unit})`}
                        style={{ ...CONTROL, paddingRight: 24, textAlign: "right", fontVariantNumeric: "tabular-nums" }}
                        onChange={e => set(i, { value: e.target.value })} />
                      <span aria-hidden style={{
                        position: "absolute", right: 9, top: "50%", transform: "translateY(-50%)",
                        fontSize: 12, color: "var(--on-variant)", pointerEvents: "none",
                      }}>{unit}</span>
                    </div>
                  </td>
                  <td style={{ ...NUM, fontWeight: 600, color: deduction ? "var(--error)" : undefined }}>
                    {calc ? `${deduction ? "−" : ""}${inr(calc.monthly_amount)}` : "—"}
                  </td>
                  <td style={{ ...NUM, color: "var(--on-variant)" }}>
                    {calc ? `${deduction ? "−" : ""}${inr(calc.annual_amount)}` : "—"}
                  </td>
                  <td style={{ ...CELL, textAlign: "center" }}>
                    {r.source_component === null && (
                      <button type="button" className="btn btn-ghost btn-sm" disabled={disabled}
                        title="Remove this component" aria-label={`Remove ${r.name || "component"}`}
                        style={{ padding: "4px 6px" }}
                        onClick={() => onChange(rows.filter((_, j) => j !== i))}>
                        <i className="ti ti-trash" />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-ghost btn-sm" disabled={disabled}
          onClick={() => onChange([...rows, blankComponent((rows.at(-1)?.order ?? 0) + 1)])}>
          <i className="ti ti-plus" /> Add component
        </button>
        <span style={{ fontSize: 11.5, color: "var(--on-variant)" }}>
          Template components can be switched off; components you add here can be removed.
          Deductions are marked in red.
        </span>
      </div>
    </div>
  );
}

// ── Summary ───────────────────────────────────────────────────────────────────

export function SalarySummary({ preview }: { preview: SalaryPreview | null }) {
  const t = preview?.totals;
  const diff = Number(t?.annual_difference ?? 0);
  const tiles: { label: string; value: string; sub?: string; tone?: string }[] = [
    { label: "Monthly earnings", value: t ? inr(t.monthly_earnings) : "—" },
    { label: "Monthly component deductions", value: t ? inr(t.monthly_deductions) : "—" },
    { label: "Annual earnings / CTC", value: t ? `${inr(t.annual_earnings)} / ${inr(t.annual_ctc)}` : "—" },
    {
      label: "Difference from CTC", value: t ? inr(t.annual_difference) : "—",
      sub: t ? (diff === 0 ? "Matches CTC" : "Not balanced automatically") : undefined,
      tone: t ? (diff === 0 ? "var(--success)" : "var(--warn)") : undefined,
    },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 10 }}>
      {tiles.map(tile => (
        <div key={tile.label} style={{ background: "var(--bg-low)", borderRadius: "var(--radius)", padding: "10px 14px" }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            {tile.label}
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4, color: tile.tone, fontVariantNumeric: "tabular-nums" }}>
            {tile.value}
          </div>
          {tile.sub && <div style={{ fontSize: 11.5, color: tile.tone, marginTop: 2 }}>{tile.sub}</div>}
        </div>
      ))}
    </div>
  );
}

// ── Previous revision comparison (collapsed) ──────────────────────────────────

export function RevisionComparison({ preview }: { preview: SalaryPreview }) {
  const prev = preview.previous;
  if (!prev || prev.components.length === 0) return null;
  return (
    <details style={{ border: "1px solid var(--outline-v)", borderRadius: "var(--radius)" }}>
      <summary style={{ cursor: "pointer", padding: "12px 14px", fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
        <i className="ti ti-history" style={{ color: "var(--on-variant)" }} />
        Compare with current revision
        <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>
          {inr(prev.annual_ctc)}/year from {prev.effective_from}
        </span>
      </summary>
      <div style={{ padding: "0 14px 14px" }}>
        <div className="table-wrap">
          <table style={{ fontSize: 12.5 }}>
            <thead>
              <tr>
                <th style={CELL}>Component</th>
                <th style={{ ...CELL, textAlign: "right" }}>Current monthly</th>
                <th style={{ ...CELL, textAlign: "right" }}>Proposed monthly</th>
                <th style={{ ...CELL, textAlign: "right" }}>Change</th>
              </tr>
            </thead>
            <tbody>
              {compareRows(prev.components, preview.components).map(c => (
                <tr key={c.name}>
                  <td style={CELL}>{c.name}</td>
                  <td style={NUM}>{inr(c.previous)}</td>
                  <td style={NUM}>{inr(c.proposed)}</td>
                  <td style={{ ...NUM, color: c.change > 0 ? "var(--success)" : c.change < 0 ? "var(--error)" : undefined }}>
                    {c.change > 0 ? "+" : ""}{inr(c.change)}
                  </td>
                </tr>
              ))}
              <tr style={{ fontWeight: 600 }}>
                <td style={CELL}>Monthly earnings</td>
                <td style={NUM}>{inr(prev.totals.monthly_earnings)}</td>
                <td style={NUM}>{inr(preview.totals.monthly_earnings)}</td>
                <td style={NUM}>{inr(Number(preview.totals.monthly_earnings) - Number(prev.totals.monthly_earnings))}</td>
              </tr>
            </tbody>
          </table>
        </div>
        {!prev.is_snapshot && (
          <p style={{ ...HELP, marginTop: 6 }}>
            The current revision has no saved components; it is shown as the structure calculates it today.
          </p>
        )}
      </div>
    </details>
  );
}
