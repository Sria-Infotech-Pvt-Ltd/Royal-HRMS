"use client";

interface Props {
  financialYearLabel: string;
  /** End of the financial year (31 March) — the closest real, non-arbitrary
   * date tied to tax declarations, since the system has no configured
   * "declaration deadline" field anywhere (confirmed in apps/payroll). */
  fyEndLabel: string;
  isApproved: boolean;
  onNavigateToTax: () => void;
}

export default function PayslipTaxNotice({ financialYearLabel, fyEndLabel, isApproved, onNavigateToTax }: Props) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 text-sm font-bold" style={{ color: "var(--on-bg)" }}>
        <i className="ti ti-file-invoice" style={{ color: "var(--primary)" }} />
        {isApproved ? "Tax declaration approved" : "Tax declaration window is open"}
      </div>
      <p className="text-xs mt-2" style={{ color: "var(--on-variant)" }}>
        {isApproved
          ? `Your ${financialYearLabel} regime and declarations were approved by HR. Further changes follow payroll approval.`
          : `Review your ${financialYearLabel} regime and declarations before ${fyEndLabel}. Changes follow payroll approval.`}
      </p>
      <button
        onClick={onNavigateToTax}
        className="text-xs font-semibold mt-3"
        style={{ background: "none", border: "none", padding: 0, color: "var(--primary)", cursor: "pointer" }}
      >
        Review declarations <i className="ti ti-arrow-right" />
      </button>
    </div>
  );
}
