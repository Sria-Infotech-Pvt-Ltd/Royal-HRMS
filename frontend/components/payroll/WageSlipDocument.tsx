"use client";

// Wage-slip payslip layout (Payroll Settings → Payslip → Layout "Wage slip"):
// letterhead, employee block, SALARY HEAD / ACTUAL / EARNING / DEDUCTION grid,
// totals and signatures — the format of the company's Excel wage slips. It
// renders the SAVED payslip only (see lib/payslipLayout): nothing is
// recalculated, and Net Salary is the stored net pay.

import type { PayslipCompanyHeader } from "@/types/payroll";
import type { PayslipCompany } from "@/components/payroll/PayslipDocument";
import { wageSlipModel, wageSlipPeriodLabel, type PayslipAmounts } from "@/lib/payslipLayout";

export interface WageSlipData extends PayslipAmounts {
  cycle_start: string;
  cycle_end: string;
  employee_name: string;
  employee_id_code: string;
  department: string;
  designation: string;
  total_working_days: number;
  lop_days: string;
  principal_employer_name: string;
  company_header: PayslipCompanyHeader | null;
  uan_display: string | null;
  esic_display: string | null;
  fixed_deduction_rows: string[];
  stamp_url: string | null;
}

const amt = (n: number) => n.toLocaleString("en-IN", { maximumFractionDigits: 2 });

export default function WageSlipDocument({ slip, company }: {
  slip: WageSlipData;
  /** Live company record — logo only; name/address come from the payslip's saved header when present. */
  company: PayslipCompany | null | undefined;
}) {
  const header = slip.company_header ?? company;
  const address = header ? [header.address, header.city, header.state, header.pin_code].filter(Boolean).join(", ") : "";
  const model = wageSlipModel(slip, slip.fixed_deduction_rows ?? []);
  const lopDays = Number(slip.lop_days ?? 0);
  const paidDays = Number(slip.total_working_days ?? 0) - lopDays;

  const left: [string, string][] = [
    ["EMPLOYEE CODE", slip.employee_id_code || "—"],
    ["EMPLOYEE NAME", slip.employee_name || "—"],
    ["DEPARTMENT", slip.department || "—"],
    ["DESIGNATION", slip.designation || "—"],
  ];
  const right: [string, string][] = [
    ...(slip.uan_display !== null ? [["PF / UAN", slip.uan_display || "—"] as [string, string]] : []),
    ...(slip.esic_display !== null ? [["ESIC NO.", slip.esic_display || "—"] as [string, string]] : []),
    ["MONTH DAYS", String(slip.total_working_days ?? 0)],
    ["PRESENT", String(paidDays)],
    ["LOP DAYS", String(lopDays)],
  ];
  const infoRows = Math.max(left.length, right.length);
  const gridRows = Math.max(model.earnings.length, model.deductions.length);

  return (
    <div className="ws-doc payslip-doc">
      <div className="ws-head">
        {slip.principal_employer_name && <div className="ws-client">{slip.principal_employer_name}</div>}
        <div className="ws-company">{header?.company_name ?? "—"}</div>
        {address && <div className="ws-address">{address}</div>}
        <div className="ws-title">{wageSlipPeriodLabel(slip.cycle_start, slip.cycle_end)}</div>
      </div>

      <table className="ws-table">
        <tbody>
          {Array.from({ length: infoRows }, (_, i) => (
            <tr key={i}>
              <th>{left[i]?.[0] ?? ""}</th><td>{left[i]?.[1] ?? ""}</td>
              <th>{right[i]?.[0] ?? ""}</th><td className="ws-num">{right[i]?.[1] ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <table className="ws-table ws-grid">
        <thead>
          <tr><th>SALARY HEAD</th><th>ACTUAL</th><th>EARNING</th><th>DEDUCTION</th><th /></tr>
        </thead>
        <tbody>
          {Array.from({ length: gridRows }, (_, i) => {
            const e = model.earnings[i];
            const d = model.deductions[i];
            return (
              <tr key={i}>
                <td>{e?.label ?? ""}</td>
                <td className="ws-num">{e && e.actual !== null ? amt(e.actual) : ""}</td>
                <td className="ws-num">{e ? amt(e.earned) : ""}</td>
                <td>{d?.label ?? ""}</td>
                <td className="ws-num">{d ? amt(d.amount) : ""}</td>
              </tr>
            );
          })}
          <tr className="ws-total">
            <td>TOTAL GROSS</td>
            <td className="ws-num">{amt(model.totals.actual)}</td>
            <td className="ws-num">{amt(model.totals.earned)}</td>
            <td>TOTAL DEDUCTION</td>
            <td className="ws-num">{amt(model.totals.deductions)}</td>
          </tr>
          <tr className="ws-total">
            <td>NET SALARY PAY</td>
            <td className="ws-num" colSpan={2}>{amt(model.totals.net)}</td>
            <td colSpan={2} />
          </tr>
        </tbody>
      </table>

      <div className="ws-sign">
        <div className="ws-sign-box">Employee Signature</div>
        <div className="ws-sign-box ws-sign-right">
          {slip.stamp_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={slip.stamp_url} alt="Company stamp" className="ws-stamp" />
          )}
          Authorized Signature
        </div>
      </div>

      <style jsx>{`
        .ws-doc { background: #fff; color: #111; width: 100%; max-width: 820px; margin-inline: auto;
          border: 1px solid #222; padding: 0; font-size: 12.5px; }
        .ws-head { position: relative; text-align: center; padding: 10px 12px 6px; border-bottom: 1px solid #222; }
        .ws-client { position: absolute; right: 10px; top: 8px; font-size: 11px; font-weight: 600; }
        .ws-company { font-size: 18px; font-weight: 800; color: #c00000; text-decoration: underline; letter-spacing: .3px; }
        .ws-address { font-size: 11.5px; margin-top: 3px; }
        .ws-title { font-weight: 700; margin-top: 6px; }
        .ws-table { width: 100%; border-collapse: collapse; }
        .ws-table th, .ws-table td { border: 1px solid #222; padding: 3px 6px; text-align: left; vertical-align: top; }
        .ws-table th { font-weight: 600; background: #fafafa; width: 22%; }
        .ws-grid thead th { background: #b4c6e7; text-align: center; width: auto; }
        .ws-num { text-align: right !important; font-variant-numeric: tabular-nums; white-space: nowrap; }
        .ws-total td { font-weight: 700; }
        .ws-sign { display: flex; justify-content: space-between; align-items: flex-end; padding: 14px 12px 8px; min-height: 110px; }
        .ws-sign-box { display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 12px; }
        .ws-sign-right { align-items: flex-end; text-align: right; }
        .ws-stamp { max-height: 80px; max-width: 140px; object-fit: contain; }
        @media (max-width: 640px) {
          .ws-doc { font-size: 11px; }
          .ws-client { position: static; text-align: right; }
          .ws-table th, .ws-table td { padding: 2px 4px; }
        }
      `}</style>
    </div>
  );
}
