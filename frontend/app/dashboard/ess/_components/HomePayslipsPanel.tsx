"use client";

// Right-column "Payslips & documents" panel. Payslip rows come from the same
// /payroll/my-payslips/ fetch HomeTab.tsx already makes for the stat tile —
// this just renders the most recent few plus a download link. "Form 16" and
// "Employment letter" have no dedicated endpoint/document-type in this repo
// (documents/_data.ts only models generic policy/form/template/other
// categories), so those two quick links route into the Documents tab itself
// rather than a fabricated direct-download URL.

interface HomePayslipRow {
  cycle:       string;
  pay_date:    string;
  net_pay:     string;
  payslip_pdf: string | null;
}

interface Props {
  payslips:     HomePayslipRow[];
  onViewAll:    () => void;
  onOpenDocuments: () => void;
}

export default function HomePayslipsPanel({ payslips, onViewAll, onOpenDocuments }: Props) {
  return (
    <div className="card">
      <div className="card-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div className="card-title"><i className="ti ti-receipt" /> Payslips &amp; documents</div>
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
            <div key={p.cycle} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 20px", borderBottom: "1px solid var(--outline-v)" }}>
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
        <button onClick={onOpenDocuments} className="btn btn-ghost btn-sm">
          <i className="ti ti-file-invoice" /> Form 16
        </button>
        <button onClick={onOpenDocuments} className="btn btn-ghost btn-sm">
          <i className="ti ti-mail" /> Employment letter
        </button>
      </div>
    </div>
  );
}
