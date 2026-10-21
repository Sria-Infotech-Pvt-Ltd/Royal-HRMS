"use client";

// Assign CTC → the employee's own salary components. Edits here change only
// this employee's new revision — never the shared structure or anyone else.
// Amounts shown come from the server preview (same calculation as payroll).

import type { SalaryComponentInput, SalaryPreview, SalaryPreviewRow } from "@/types/payroll";
import { CALCULATION_LABEL, COMPONENT_TYPE_LABEL, ROLE_LABEL, blankComponent, compareRows } from "@/lib/salaryComponents";

const inr = (n: number | string | null) =>
  n === null ? "—" : `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

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
  const totals = preview?.totals;
  const diff = Number(totals?.annual_difference ?? 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="table-wrap">
        <table style={{ fontSize: 12.5 }}>
          <thead>
            <tr>
              <th style={{ width: 40 }}>On</th>
              <th>Component</th>
              <th>Type</th>
              <th>Payslip line</th>
              <th>Method</th>
              <th style={{ width: 110 }}>Value</th>
              <th style={{ textAlign: "right" }}>Monthly</th>
              <th style={{ textAlign: "right" }}>Annual</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const calc = amounts.get(r.name.trim());
              return (
                <tr key={i} style={r.is_enabled ? undefined : { opacity: 0.55 }}>
                  <td>
                    <input type="checkbox" checked={r.is_enabled} disabled={disabled}
                      aria-label={`Include ${r.name || "component"}`}
                      onChange={e => set(i, { is_enabled: e.target.checked })} />
                  </td>
                  <td>
                    <input className="field-input" value={r.name} disabled={disabled} maxLength={100}
                      placeholder="Component name" style={{ minWidth: 130 }}
                      onChange={e => set(i, { name: e.target.value })} />
                    {r.source_component === null && <div style={{ fontSize: 10.5, color: "var(--on-variant)" }}>Added for this employee</div>}
                  </td>
                  <td>
                    <select className="field-input" value={r.component_type} disabled={disabled}
                      onChange={e => set(i, { component_type: e.target.value as SalaryComponentInput["component_type"] })}>
                      {Object.entries(COMPONENT_TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </td>
                  <td>
                    <select className="field-input" value={r.role} disabled={disabled}
                      onChange={e => set(i, { role: e.target.value as SalaryComponentInput["role"] })}>
                      {Object.entries(ROLE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </td>
                  <td>
                    <select className="field-input" value={r.calculation_type} disabled={disabled}
                      onChange={e => set(i, { calculation_type: e.target.value as SalaryComponentInput["calculation_type"] })}>
                      {Object.entries(CALCULATION_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </td>
                  <td>
                    <input className="field-input" type="number" min={0} step="any" value={r.value} disabled={disabled}
                      onChange={e => set(i, { value: e.target.value })} />
                  </td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap", color: r.component_type === "deduction" ? "var(--error)" : undefined }}>
                    {calc ? `${r.component_type === "deduction" ? "−" : ""}${inr(calc.monthly_amount)}` : "—"}
                  </td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap", color: "var(--on-variant)" }}>
                    {calc ? inr(calc.annual_amount) : "—"}
                  </td>
                  <td>
                    {r.source_component === null && (
                      <button type="button" className="btn btn-ghost btn-sm" disabled={disabled} title="Remove"
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

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-ghost btn-sm" disabled={disabled}
          onClick={() => onChange([...rows, blankComponent((rows.at(-1)?.order ?? 0) + 1)])}>
          <i className="ti ti-plus" /> Add component for this employee
        </button>
        {totals && (
          <div style={{ fontSize: 12.5, display: "grid", gridTemplateColumns: "auto auto", gap: "2px 16px", textAlign: "right" }}>
            <span style={{ color: "var(--on-variant)" }}>Monthly earnings</span><strong>{inr(totals.monthly_earnings)}</strong>
            <span style={{ color: "var(--on-variant)" }}>Monthly component deductions</span><span>{inr(totals.monthly_deductions)}</span>
            <span style={{ color: "var(--on-variant)" }}>Annual earnings / CTC</span>
            <span>{inr(totals.annual_earnings)} / {inr(totals.annual_ctc)}</span>
            <span style={{ color: "var(--on-variant)" }}>Difference from CTC</span>
            <strong style={{ color: diff === 0 ? "var(--success)" : "var(--warn)" }}>{inr(totals.annual_difference)}</strong>
          </div>
        )}
      </div>

      {preview?.previous && preview.previous.components.length > 0 && (
        <details>
          <summary style={{ cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}>
            Compare with current revision ({inr(preview.previous.annual_ctc)}/year from {preview.previous.effective_from})
          </summary>
          <div className="table-wrap" style={{ marginTop: 8 }}>
            <table style={{ fontSize: 12.5 }}>
              <thead>
                <tr><th>Component</th><th style={{ textAlign: "right" }}>Current monthly</th>
                  <th style={{ textAlign: "right" }}>Proposed monthly</th><th style={{ textAlign: "right" }}>Change</th></tr>
              </thead>
              <tbody>
                {compareRows(preview.previous.components, preview.components).map(c => (
                  <tr key={c.name}>
                    <td>{c.name}</td>
                    <td style={{ textAlign: "right" }}>{inr(c.previous)}</td>
                    <td style={{ textAlign: "right" }}>{inr(c.proposed)}</td>
                    <td style={{ textAlign: "right", color: c.change > 0 ? "var(--success)" : c.change < 0 ? "var(--error)" : undefined }}>
                      {c.change > 0 ? "+" : ""}{inr(c.change)}
                    </td>
                  </tr>
                ))}
                <tr style={{ fontWeight: 600 }}>
                  <td>Monthly earnings</td>
                  <td style={{ textAlign: "right" }}>{inr(preview.previous.totals.monthly_earnings)}</td>
                  <td style={{ textAlign: "right" }}>{inr(preview.totals.monthly_earnings)}</td>
                  <td style={{ textAlign: "right" }}>
                    {inr(Number(preview.totals.monthly_earnings) - Number(preview.previous.totals.monthly_earnings))}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          {!preview.previous.is_snapshot && (
            <p className="field-help" style={{ marginTop: 4 }}>
              The current revision has no saved components; it is shown as the structure calculates it today.
            </p>
          )}
        </details>
      )}
    </div>
  );
}
