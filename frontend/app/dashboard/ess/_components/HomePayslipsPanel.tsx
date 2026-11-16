"use client";

// Right-column "Payslips & documents" panel. Payslip rows come from the same /payroll/my-payslips/ fetch HomeTab.tsx already makes
// for the stat tile - this just renders the most recent few plus a download link. "Form 16" and "Employment letter" are real PDFs
// generated on demand for the signed-in employee (GET /payroll/my-payslips/form16/<fy>/pdf/ and GET /employees/me/employment-letter/,
// the same downloads the Tax and Employment tabs offer), so both buttons download them. Nothing here sends an employee to the
// company Document Center: that is the policies / forms / templates library, not a place for an employee's own documents.

import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";

interface HomePayslipRow {
  cycle:       string;
  pay_date:    string;
  net_pay:     string;
  payslip_pdf: string | null;
}

interface Props {
  payslips:   HomePayslipRow[];
  // Start year of the previous financial year when it actually has a payslip (see HomeTab), else null. The Form 16 button is
  // hidden rather than shown unconditionally: a fresh joiner with no closed FY behind them has no Form 16 yet.
  form16FyStartYear: number | null;
  onViewAll:  () => void;
}

export default function HomePayslipsPanel({ payslips, form16FyStartYear, onViewAll }: Props) {
  return (
    <div className="card">
      <div className="card-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <div className="card-title"><i className="ti ti-receipt" /> Payslips &amp; documents</div>
          <p style={{ margin: "4px 0 0", fontSize: 11, color: "var(--on-variant)" }}>Your latest secure employee documents.</p>
        </div>
        <button onClick={onViewAll} className="btn btn-ghost btn-sm">
          View all <i className="ti ti-arrow-right" />
        </button>
      </div>

      {payslips.length === 0 ? (
        <div className="empty-state" style={{ padding: "28px 20px" }}>
          <i className="ti ti-file-off" />
          <p>No payslips yet.</p>
        </div>
      ) : (
        <div>
          {payslips.slice(0, 4).map(p => (
            <div key={p.cycle} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px", borderBottom: "1px solid var(--outline-v)" }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{p.cycle}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)" }}>₹{Number(p.net_pay).toLocaleString("en-IN")}</div>
              </div>
              {p.payslip_pdf ? (
                <a href={p.payslip_pdf} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm">
                  <i className="ti ti-download" /> Download
                </a>
              ) : (
                <span style={{ fontSize: 11, color: "var(--on-variant)" }}>Not available</span>
              )}
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 10, padding: "14px 20px", borderTop: "1px solid var(--outline-v)" }}>
        {/* Content-Disposition: attachment makes the browser download each PDF, so no target="_blank" is needed. */}
        {form16FyStartYear !== null && (
          <a href={`${API_BASE}${API.payroll.form16Pdf(form16FyStartYear)}`} className="btn btn-ghost btn-sm">
            <i className="ti ti-download" /> Form 16
          </a>
        )}
        <a href={`${API_BASE}${API.employees.myEmploymentLetterPdf}`} className="btn btn-ghost btn-sm">
          <i className="ti ti-download" /> Employment letter
        </a>
      </div>
    </div>
  );
}
