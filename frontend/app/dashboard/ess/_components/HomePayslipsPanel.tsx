"use client";

// "Payslips & documents" card — the latest published payslips with real
// download links, plus shortcuts to Form 16 / the employment letter.

import type { EssTabId } from "./HomeTab";

interface HomePayslipRow {
  cycle:       string;
  pay_date:    string;
  net_pay:     string;
  payslip_pdf: string | null;
}

interface Props {
  payslips:   HomePayslipRow[];
  onViewAll:  () => void;
  onNavigate: (tab: EssTabId) => void;
}

export default function HomePayslipsPanel({ payslips, onViewAll, onNavigate }: Props) {
  return (
    <section className="ess-card">
      <h2>Payslips &amp; documents</h2>
      <p>Your latest secure employee documents.</p>
      <div className="ess-list">
        {payslips.slice(0, 3).map(p => (
          <div key={p.cycle} className="ess-row">
            <button type="button" className="ess-row ess-row-link" onClick={onViewAll}>
              <div><b>{p.cycle} payslip</b><small>₹{Number(p.net_pay).toLocaleString("en-IN")} · PDF</small></div>
              <span className="row-go" aria-hidden="true">›</span>
            </button>
            {p.payslip_pdf
              ? <a className="btn btn-ghost btn-sm" href={p.payslip_pdf} target="_blank" rel="noopener noreferrer">Download</a>
              : <span className="state">PENDING</span>}
          </div>
        ))}
        {payslips.length === 0 && (
          <div className="ess-row"><div><b>No payslips yet</b><small>Published payslips will appear here.</small></div></div>
        )}
        <button type="button" className="ess-row ess-row-link" onClick={() => onNavigate("payslips")}>
          <div><b>Form 16</b><small>Annual tax certificate · PDF</small></div>
          <span className="row-go" aria-hidden="true">›</span>
        </button>
        <button type="button" className="ess-row ess-row-link" onClick={() => onNavigate("employment")}>
          <div><b>Employment letter</b><small>Verified document · PDF</small></div>
          <span className="row-go" aria-hidden="true">›</span>
        </button>
      </div>
    </section>
  );
}
