"use client";

// Self-service "Payslips & tax" tab, laid out as the Employee Directory reference: header with month selector and
// download, a net-pay hero, earnings / deductions / employer-contribution tables, year-to-date summary, the tax
// declaration notice and previous statements. Every figure is real (payslips, profile, payroll settings, tax
// declaration and financial-year endpoints) — nothing is fabricated; what the system cannot know (Form 16) is
// shown as unavailable rather than made up.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";
import { formatDate } from "@/lib/formatDate";
import { logPayslipDownload } from "../../my-payslip/_components/downloadAudit";
import {
  INR, computeYtd, currentFinancialYearStart, financialYearLabel, fmtMonth, fyEndLabel,
  type ApiFinancialYearConfig, type ApiMe, type ApiPayrollSettings, type ApiPayslip,
  type ApiTaxDeclarationBrief, type PagedResponse,
} from "../../my-payslip/_components/types";
import { tr } from "@/lib/i18n/tr";

interface Line { label: string; value: number }

function PayTable({ title, subtitle, lines, totalLabel, total }: {
  title: string; subtitle: string; lines: Line[]; totalLabel: string; total: number;
}) {
  return (
    <div className="ess-card">
      <h2>{title}</h2>
      <p>{subtitle}</p>
      <table className="pay-table">
        <thead><tr><th>{tr("COMPONENT")}</th><th>{tr("AMOUNT")}</th></tr></thead>
        <tbody>
          {lines.map(line => <tr key={line.label}><td>{line.label}</td><td>{INR(line.value)}</td></tr>)}
          <tr className="pay-total"><td>{totalLabel}</td><td>{INR(total)}</td></tr>
        </tbody>
      </table>
    </div>
  );
}

function earningsOf(slip: ApiPayslip): Line[] {
  const others = Object.entries(slip.other_earnings ?? {}).map(([label, amount]) => ({ label, value: Number(amount) }));
  return [
    { label: tr("Basic salary"), value: Number(slip.basic) },
    { label: tr("House rent allowance"), value: Number(slip.hra) },
    { label: tr("Special allowance"), value: Number(slip.special_allowance) },
    ...others,
    { label: tr("Bonus"), value: Number(slip.bonus) },
    { label: tr("Reimbursements"), value: Number(slip.reimbursements) },
  ].filter(line => line.value !== 0);
}

function deductionsOf(slip: ApiPayslip): Line[] {
  const other = Number(slip.esi_employee) + Number(slip.lwf_employee) + Number(slip.adjustments_deduction) + Number(slip.lop_deduction);
  return [
    { label: tr("Provident fund"), value: Number(slip.pf_employee) },
    { label: tr("Professional tax"), value: Number(slip.pt_deduction) },
    { label: tr("Income tax (TDS)"), value: Number(slip.income_tax) },
    ...(other > 0 ? [{ label: tr("Other deductions"), value: other }] : []),
  ];
}

export default function EssPayslipsTab({ onNavigateToTax }: { onNavigateToTax: () => void }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const slips = useFetch<PagedResponse<ApiPayslip>>(API.payroll.myPayslips);
  const { data: me } = useFetch<ApiMe>(API.employees.me);
  const { data: settings } = useFetch<ApiPayrollSettings>(API.payroll.settings);
  const { data: taxDeclaration } = useFetch<ApiTaxDeclarationBrief>(API.payroll.myTaxDeclaration);
  const { data: fyConfig } = useFetch<ApiFinancialYearConfig>(API.settings.financialYear);

  const payslips = slips.data?.results ?? [];
  const slip = payslips.find(item => item.id === selectedId) ?? payslips[0] ?? null;
  const head = (
    <div className="ess-pagehead">
      <div>
        <h2>{tr("Payslips & tax")}</h2>
        <p>{tr("Understand your salary, deductions, taxes and employer contributions.")}</p>
      </div>
      {slip && (
        <div className="pay-actions">
          <select className="pay-selector" aria-label={tr("Payslip month")} value={slip.id} onChange={event => setSelectedId(event.target.value)}>
            {payslips.map(item => <option key={item.id} value={item.id}>{fmtMonth(item.cycle_start)}</option>)}
          </select>
          <a className="rvbtn pri" href={`${API_BASE}${API.payroll.payslipPdf(slip.id)}`} onClick={() => logPayslipDownload(slip.id)}>{tr("Download payslip")}</a>
        </div>
      )}
    </div>
  );

  if (slips.loading) return <section className="ess-page">{head}<div className="ess-card"><p>{tr("Loading your payslips…")}</p></div></section>;
  if (slips.error) return <section className="ess-page">{head}<div className="alert alert-error">{tr("Failed to load payslips. Please refresh.")}</div></section>;
  if (!slip) {
    return (
      <section className="ess-page">
        {head}
        <div className="ess-card">
          <h2>{tr("No payslips yet")}</h2>
          <p>{tr("Your payslips will appear here once payroll is processed for your account.")}</p>
        </div>
      </section>
    );
  }

  const month = fmtMonth(slip.cycle_start);
  const gross = Number(slip.gross_earnings);
  const deductionsTotal = Number(slip.total_deductions);
  const bankMasked = me?.profile?.account_number_masked ? tr("A/c {number}", { number: me.profile.account_number_masked }) : null;
  const credited = [tr("Credited on {date}", { date: formatDate(slip.pay_date) }), me?.profile?.bank_name, bankMasked].filter(Boolean).join(" · ");
  const fyStart = currentFinancialYearStart(fyConfig?.financial_year_start_month ?? "April");
  const fyLabel = fyConfig?.current_financial_year ?? financialYearLabel(fyStart);
  const ytd = computeYtd(payslips, fyStart);
  const gratuity = settings ? Number(slip.basic) * Number(settings.gratuity_rate) / 100 : 0;
  const employer: Line[] = [
    { label: tr("Employer PF"), value: Number(slip.pf_employer) },
    { label: tr("Gratuity provision"), value: gratuity },
    { label: tr("Insurance premium"), value: Number(slip.esi_employer) },
  ];
  const approved = taxDeclaration?.status === "approved";

  return (
    <section className="ess-page">
      {head}

      <div className="pay-hero">
        <div>
          <small>{tr("NET PAY ·")} <span>{month.toUpperCase()}</span></small>
          <h3>{INR(slip.net_pay)}</h3>
          <p>{credited}</p>
        </div>
        <div className="pay-hero-side">
          <div><small>{tr("GROSS EARNINGS")}</small><b>{INR(gross)}</b></div>
          <div><small>{tr("TOTAL DEDUCTIONS")}</small><b>{INR(deductionsTotal)}</b></div>
          <div><small>{tr("PAID DAYS")}</small><b>{slip.total_working_days - Number(slip.lop_days)} / {slip.total_working_days}</b></div>
          <div><small>{tr("PF NUMBER")}</small><b>{me?.profile?.pf_number || "—"}</b></div>
        </div>
      </div>

      <div className="pay-layout">
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="ess-grid">
            <PayTable title={tr("Earnings")} subtitle={tr("{month} payroll components.", { month })} lines={earningsOf(slip)} totalLabel={tr("Total earnings")} total={gross} />
            <PayTable title={tr("Deductions")} subtitle={tr("{month} payroll components.", { month })} lines={deductionsOf(slip)} totalLabel={tr("Total deductions")} total={deductionsTotal} />
          </div>
          <div className="ess-card">
            <h2>{tr("Year-to-date summary")}</h2>
            <p>{tr("{range} cumulative payroll.", { range: ytd.monthRangeLabel })}</p>
            <div className="ess-metrics ess-metrics-3">
              <article className="ess-metric"><i>{tr("GROSS EARNINGS")}</i><b>{INR(ytd.gross)}</b><span>{ytd.periodCount === 1 ? tr("{count} payroll period", { count: ytd.periodCount }) : tr("{count} payroll periods", { count: ytd.periodCount })}</span></article>
              <article className="ess-metric"><i>{tr("INCOME TAX")}</i><b>{INR(ytd.incomeTax)}</b><span>{tr("deducted to date")}</span></article>
              <article className="ess-metric"><i>{tr("NET PAY")}</i><b>{INR(ytd.net)}</b><span>{tr("credited to date")}</span></article>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="ess-card">
            <h2>{tr("Employer contributions")}</h2>
            <p>{tr("Benefits paid in addition to net salary.")}</p>
            <table className="pay-table">
              <tbody>
                {employer.map(line => <tr key={line.label}><td>{line.label}</td><td>{INR(line.value)}</td></tr>)}
                <tr className="pay-total"><td>{tr("Total")}</td><td>{INR(employer.reduce((sum, line) => sum + line.value, 0))}</td></tr>
              </tbody>
            </table>
          </div>

          <div className="pay-callout">
            <b>{approved ? tr("Tax declaration approved") : tr("Tax declaration window is open")}</b>
            <p>
              {approved
                ? tr("Your {year} regime and declarations were approved. Further changes follow payroll approval.", { year: taxDeclaration?.financial_year ? `FY ${taxDeclaration.financial_year}` : fyLabel })
                : tr("Review your {year} regime and declarations before {date}. Changes follow payroll approval.", { year: taxDeclaration?.financial_year ? `FY ${taxDeclaration.financial_year}` : fyLabel, date: fyEndLabel(fyStart) })}
            </p>
            <button className="rvbtn ghost" type="button" style={{ marginTop: 10 }} onClick={onNavigateToTax}>{tr("Review declarations")}</button>
          </div>

          <div className="ess-card pay-history">
            <h2>{tr("Previous statements")}</h2>
            <p>{tr("Secure downloads are access logged.")}</p>
            <div className="ess-list">
              {payslips.map(item => (
                <div className="ess-row" key={item.id}>
                  <div><b>{fmtMonth(item.cycle_start)}</b><small>{tr("{amount} · PDF", { amount: INR(item.net_pay) })}</small></div>
                  <a className="rvbtn ghost" href={`${API_BASE}${API.payroll.payslipPdf(item.id)}`} onClick={() => logPayslipDownload(item.id)}>{tr("Download")}</a>
                </div>
              ))}
              <div className="ess-row">
                <div><b>{tr("Form 16 · {year}", { year: fyLabel })}</b><small>{tr("Tax certificate · not yet available")}</small></div>
                <button className="rvbtn ghost" type="button" disabled title={tr("Form 16 generation is not yet available")}>{tr("Download")}</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="pay-callout">
        <b>{tr("Confidential payroll document")}</b>
        <p>{tr("This payslip contains personal and financial information. Downloads are generated for the signed-in employee and recorded in the audit trail.")}</p>
      </div>
    </section>
  );
}
