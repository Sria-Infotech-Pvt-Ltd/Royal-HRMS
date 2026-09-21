"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export interface BasicPayDraft {
  tax_regime: string;
  payment_method: string;
}

export const EMPTY_BASIC_PAY: BasicPayDraft = { tax_regime: "new", payment_method: "bank_transfer" };

const PAYMENT_METHODS = [["bank_transfer", "Bank Transfer – NEFT"], ["cheque", "Cheque"], ["cash", "Cash"]];

interface Breakdown {
  basic: number; hra: number; special_allowance: number; other_earnings: Record<string, number>;
  gross_earnings: number; employer_pf: number; employer_eps: number; gratuity_provision: number;
  employer_esi: number; total_employer_contributions: number; employee_pf: number; employee_esi: number;
  pt_deduction: number; total_deductions: number; monthly_cost_to_company: number;
  annual_cost_to_company: number; net_pay: number;
}

const INR = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

interface Props {
  annualCtc: string;
  salaryStructureId: string;
  branchName: string;
  value: BasicPayDraft;
  onChange: (next: BasicPayDraft) => void;
}

// Live-computed via the estimate_salary_breakdown() preview endpoint — see
// that service's own module docstring for why it's a preview, not the real
// payroll engine.
export default function BasicPayStep({ annualCtc, salaryStructureId, branchName, value, onChange }: Props) {
  const [breakdown, setBreakdown] = useState<Breakdown | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!annualCtc) { setBreakdown(null); return; }
    setLoading(true);
    clientApi.post<{ data: Breakdown }>(API.payroll.salaryPreview, {
      annual_ctc: annualCtc,
      ...(salaryStructureId ? { salary_structure: salaryStructureId } : {}),
    })
      .then(r => setBreakdown(r.data?.data ?? null))
      .catch(() => setBreakdown(null))
      .finally(() => setLoading(false));
  }, [annualCtc, salaryStructureId, branchName]);

  if (!annualCtc) {
    return (
      <div className="mstep on">
        <div className="hint">
          Set an Annual fixed CTC on the Employment step first — the earnings breakdown estimates from that.
        </div>
      </div>
    );
  }

  return (
    <div className="mstep on">

      {loading && <p className="text-[12.5px]" style={{ color: "var(--on-variant)" }}>Estimating…</p>}

      {breakdown && (
        <>
          <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Earnings</div>
          <table className="w-full text-[13px] mb-5" style={{ borderCollapse: "collapse" }}>
            <tbody>
              <Row label="Basic Pay" value={breakdown.basic} />
              <Row label="House Rent Allowance" value={breakdown.hra} />
              {Object.entries(breakdown.other_earnings).map(([name, amt]) => <Row key={name} label={name} value={amt} />)}
              <Row label="Special Allowance" value={breakdown.special_allowance} />
              <Row label="Monthly gross" value={breakdown.gross_earnings} bold />
            </tbody>
          </table>

          <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Employer contributions</div>
          <table className="w-full text-[13px] mb-5" style={{ borderCollapse: "collapse" }}>
            <tbody>
              <Row label="Employer PF (EPF)" value={breakdown.employer_pf} />
              <Row label="Employer Pension (EPS)" value={breakdown.employer_eps} />
              <Row label="Gratuity Provision" value={breakdown.gratuity_provision} />
              <Row label="Employer ESI" value={breakdown.employer_esi} />
            </tbody>
          </table>

          <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Statutory deductions</div>
          <table className="w-full text-[13px] mb-5" style={{ borderCollapse: "collapse" }}>
            <tbody>
              <Row label="Employee PF" value={breakdown.employee_pf} />
              <Row label="Employee ESI" value={breakdown.employee_esi} />
              <Row label="Professional Tax" value={breakdown.pt_deduction} />
            </tbody>
          </table>

          <div className="rounded-lg p-3.5 space-y-1.5 mb-5" style={{ background: "var(--bg-low)" }}>
            <SummaryRow label="Monthly gross — paid to the employee" value={breakdown.gross_earnings} />
            <SummaryRow label="Employer contributions — on top of gross" value={breakdown.total_employer_contributions} />
            <SummaryRow label="Monthly cost to company" value={breakdown.monthly_cost_to_company} />
            <SummaryRow label="Annual cost to company" value={breakdown.annual_cost_to_company} />
            <SummaryRow label="Statutory deductions" value={-breakdown.total_deductions} />
            <SummaryRow label="Net take-home before income tax" value={breakdown.net_pay} bold />
          </div>
        </>
      )}

      <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Employee declarations</div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[12.5px] font-semibold mb-1.5">Tax regime</label>
          <select value={value.tax_regime} onChange={e => onChange({ ...value, tax_regime: e.target.value })}
            className="w-full px-3.5 py-2.5 rounded-lg border border-[var(--outline-v)] text-[13px] bg-[var(--surface)] cursor-pointer">
            <option value="new">New regime (115BAC)</option>
            <option value="old">Old regime</option>
          </select>
        </div>
        <div>
          <label className="block text-[12.5px] font-semibold mb-1.5">Payment method</label>
          <select value={value.payment_method} onChange={e => onChange({ ...value, payment_method: e.target.value })}
            className="w-full px-3.5 py-2.5 rounded-lg border border-[var(--outline-v)] text-[13px] bg-[var(--surface)] cursor-pointer">
            {PAYMENT_METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, bold }: { label: string; value: number; bold?: boolean }) {
  return (
    <tr style={{ borderTop: "1px solid var(--outline-v)" }}>
      <td style={{ padding: "7px 0", fontWeight: bold ? 700 : 400 }}>{label}</td>
      <td style={{ padding: "7px 0", textAlign: "right", fontWeight: bold ? 700 : 400 }}>{INR(value)}</td>
    </tr>
  );
}

function SummaryRow({ label, value, bold }: { label: string; value: number; bold?: boolean }) {
  return (
    <div className="flex justify-between text-[12.5px]" style={{ fontWeight: bold ? 700 : 400 }}>
      <span style={{ color: bold ? "var(--on-bg)" : "var(--on-variant)" }}>{label}</span>
      <span>{INR(value)}</span>
    </div>
  );
}
