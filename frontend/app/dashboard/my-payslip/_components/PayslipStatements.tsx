"use client";

import type { ApiPayslip } from "./types";
import { INR, fmtMonth } from "./types";
import { logPayslipDownload } from "./downloadAudit";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";

function StatementRow({ label, amountLabel, downloadHref, payslipId, disabledTitle }: {
  label: string; amountLabel: string; downloadHref: string | null; payslipId: string | null; disabledTitle?: string;
}) {
  return (
    <div className="flex justify-between items-center py-3 border-b border-[var(--outline-v)] last:border-0">
      <div>
        <div className="text-sm font-semibold" style={{ color: "var(--on-bg)" }}>{label}</div>
        <div className="text-xs mt-0.5" style={{ color: "var(--on-variant)" }}>{amountLabel}</div>
      </div>
      {downloadHref ? (
        <a
          href={downloadHref}
          className="text-xs font-semibold"
          style={{ color: "var(--primary)" }}
          onClick={() => payslipId && logPayslipDownload(payslipId)}
        >
          Download
        </a>
      ) : (
        <span className="text-xs font-semibold" style={{ color: "var(--outline)", cursor: "not-allowed" }} title={disabledTitle}>
          Download
        </span>
      )}
    </div>
  );
}

interface Props {
  payslips: ApiPayslip[];
  currentFinancialYearLabel: string;
}

export default function PayslipStatements({ payslips, currentFinancialYearLabel }: Props) {
  return (
    <div className="card">
      <div className="px-4 py-3 border-b" style={{ borderColor: "var(--outline-v)" }}>
        <div className="text-sm font-bold" style={{ color: "var(--on-bg)" }}>Previous statements</div>
        <div className="text-xs mt-0.5" style={{ color: "var(--on-variant)" }}>Secure downloads are access logged.</div>
      </div>
      <div className="px-4 py-1">
        {payslips.map(p => (
          <StatementRow
            key={p.id}
            label={fmtMonth(p.cycle_start)}
            amountLabel={`Payslip · ${INR(p.net_pay)}`}
            downloadHref={`${API_BASE}${API.payroll.payslipPdf(p.id)}`}
            payslipId={p.id}
            disabledTitle="PDF not yet available for this payslip"
          />
        ))}
        {/* Form 16 generation is explicitly out of scope for this build (no
            generator/model/endpoint exists anywhere in apps/payroll) — the
            row is shown per spec but its download is always disabled rather
            than pointing at a fake or broken link. */}
        <StatementRow
          label={`Form 16 · ${currentFinancialYearLabel}`}
          amountLabel="Annual tax certificate"
          downloadHref={null}
          payslipId={null}
          disabledTitle="Form 16 generation is not yet available"
        />
      </div>
    </div>
  );
}
