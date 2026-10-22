"use client";

// Payroll → run → employee: the employee's saved payslip, read-only.
// GET /payroll/payslips/<id>/ (payroll.view; HR sees any payslip in scope,
// an employee only their own). Amounts are the saved payslip values — nothing
// is recalculated. Print uses the browser's print dialog ("Save as PDF").

import { use, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import PayslipDocument, { fmtDate, type PayslipCompany } from "@/components/payroll/PayslipDocument";
import type { EmployeePayslip } from "@/types/payroll";

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft", sent: "Sent", acknowledged: "Acknowledged", queried: "Queried", resolved: "Resolved", paid: "Paid",
};

const PRINT_CSS = `
  @media screen { .payslip-print-root { display: none; } }
  @media print {
    @page { size: A4; margin: 10mm; }
    body > *:not(.payslip-print-root) { display: none !important; }
    .payslip-print-root { display: block !important; }
    .payslip-print-root, .payslip-print-root * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .payslip-print-root .payslip-doc { box-shadow: none !important; }
  }
`;

/** Print-only copy of the payslip, placed directly under <body> so the print
 *  stylesheet can hide the rest of the app (same approach as the ID card). */
function PrintCopy({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return createPortal(
    <div className="payslip-print-root"><style>{PRINT_CSS}</style>{children}</div>,
    document.body,
  );
}

export default function PayslipViewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: slip, loading, error } = useFetch<EmployeePayslip>(API.payroll.payslip(id));
  const { data: company } = useFetch<PayslipCompany>(API.settings.company);

  if (loading) {
    return (
      <div className="empty-state">
        <i className="ti ti-loader-2 animate-spin text-2xl" />
        <div className="empty-state-desc mt-2">Loading payslip…</div>
      </div>
    );
  }
  if (error || !slip) {
    return (
      <div>
        <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error || "Payslip not found."}</div>
        <button className="btn btn-ghost" onClick={() => router.back()}><i className="ti ti-arrow-left" /> Back</button>
      </div>
    );
  }

  const isPaid = slip.status === "paid";
  const zeroPay = Number(slip.gross_earnings) <= 0 && Number(slip.net_pay) <= 0 && Number(slip.annual_ctc) > 0;
  const doc = (
    <PayslipDocument
      slip={slip}
      company={company}
      strip={[
        ["Employee", slip.employee_name || "—"],
        ["Employee ID", slip.employee_id_code || "—"],
        ["Department", slip.department || "—"],
        ["Branch", slip.branch || "—"],
      ]}
      netLabel={isPaid ? "Net Salary Paid" : "Net Salary"}
      netSubline={isPaid && slip.paid_at
        ? `Paid on ${fmtDate(slip.paid_at)}`
        : `Pay date ${fmtDate(slip.pay_date)} · ${STATUS_LABEL[slip.status] ?? slip.status}`}
    />
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="page-header">
        <div>
          <div className="page-title">Payslip — {slip.employee_name}</div>
          <div className="page-sub">
            {slip.employee_id_code} · {fmtDate(slip.cycle_start)} – {fmtDate(slip.cycle_end)} ·{" "}
            <span className={`badge ${isPaid ? "badge-success" : "badge-neutral"}`}>{STATUS_LABEL[slip.status] ?? slip.status}</span>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push(`/dashboard/payroll/runs/${slip.cycle}`)}>
            <i className="ti ti-arrow-left" /> Payroll run
          </button>
          {slip.payslip_pdf && (
            <a className="btn btn-ghost" href={slip.payslip_pdf} target="_blank" rel="noreferrer">
              <i className="ti ti-download" /> Download PDF
            </a>
          )}
          <button className="btn btn-filled" onClick={() => window.print()} title="Print, or choose “Save as PDF” in the print dialog">
            <i className="ti ti-printer" /> Print / Save PDF
          </button>
        </div>
      </div>

      {zeroPay && (
        <div className="alert alert-warn" style={{ marginBottom: 0 }}>
          <i className="ti ti-alert-triangle" />
          <span>
            This payslip has ₹0 earnings although a CTC of ₹{Number(slip.annual_ctc).toLocaleString("en-IN")}/year is set —
            the employee&apos;s salary components produced no amount. These are the saved figures; they are not recalculated here.
          </span>
        </div>
      )}
      {isPaid && (
        <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
          <i className="ti ti-lock" /> Paid payslip — read-only.
        </div>
      )}

      {doc}
      <PrintCopy>{doc}</PrintCopy>
    </div>
  );
}
