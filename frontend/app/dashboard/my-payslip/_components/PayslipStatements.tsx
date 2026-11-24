"use client";

import type { ApiPayslip } from "./types";
import { INR, fmtMonth } from "./types";
import { logPayslipDownload } from "./downloadAudit";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";
import { tr } from "@/lib/i18n/tr";

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
          {tr("Download")}
        </a>
      ) : (
        <span className="text-xs font-semibold" style={{ color: "var(--outline)", cursor: "not-allowed" }} title={disabledTitle}>
          {tr("Download")}
        </span>
      )}
    </div>
  );
}

interface Props {
  payslips: ApiPayslip[];
  currentFinancialYearLabel: string;
  fyStartYear: number;
}

export default function PayslipStatements({ payslips, currentFinancialYearLabel, fyStartYear }: Props) {
  return (
    <div className="card">
      <div className="px-4 py-3 border-b" style={{ borderColor: "var(--outline-v)" }}>
        <div className="text-sm font-bold" style={{ color: "var(--on-bg)" }}>{tr("Previous statements")}</div>
        <div className="text-xs mt-0.5" style={{ color: "var(--on-variant)" }}>{tr("Secure downloads are access logged.")}</div>
      </div>
      <div className="px-4 py-1">
        {payslips.map(p => (
          <StatementRow
            key={p.id}
            label={fmtMonth(p.cycle_start)}
            amountLabel={tr("{amount} · PDF", { amount: INR(p.net_pay) })}
            downloadHref={`${API_BASE}${API.payroll.payslipPdf(p.id)}`}
            payslipId={p.id}
            disabledTitle={tr("PDF not yet available for this payslip")}
          />
        ))}
        <StatementRow
          label={tr("Form 16 · {year}", { year: currentFinancialYearLabel })}
          amountLabel={tr("Tax certificate · PDF")}
          downloadHref={`${API_BASE}${API.payroll.form16Pdf(fyStartYear)}`}
          payslipId={null}
        />
      </div>
    </div>
  );
}
