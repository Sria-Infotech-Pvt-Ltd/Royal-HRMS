"use client";

// ESS "Payslips & tax" screen — strict-replication pass. All figures still
// come from the existing my-payslips / employees.me / payroll.settings /
// tax-declarations.me endpoints (see _components/types.ts, PayslipBreakdown.tsx
// and PayslipYtdSummary.tsx for the per-field real vs. computed vs.
// flagged-as-unavailable notes). No fabricated amounts.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import PayslipHeader from "./_components/PayslipHeader";
import PayslipHero from "./_components/PayslipHero";
import PayslipBreakdown from "./_components/PayslipBreakdown";
import PayslipYtdSummary from "./_components/PayslipYtdSummary";
import PayslipTaxNotice from "./_components/PayslipTaxNotice";
import PayslipStatements from "./_components/PayslipStatements";
import PayslipConfidentialNotice from "./_components/PayslipConfidentialNotice";
import {
  currentFinancialYearStart, financialYearLabel, fyEndLabel, computeYtd,
  type ApiPayslip, type ApiMe, type ApiPayrollSettings, type ApiTaxDeclarationBrief,
  type ApiFinancialYearConfig, type PagedResponse,
} from "./_components/types";

interface Props {
  /** Wired by the ESS shell to switch to its Tax tab (see _client.tsx). Falls
   * back to a plain route push when this page is rendered standalone at
   * /dashboard/my-payslip, which lands on the ESS shell's default Home tab
   * rather than directly on Tax — a known minor limitation outside a full
   * client-side tab router. */
  onNavigateToTax?: () => void;
}

export default function MyPayslipPage({ onNavigateToTax }: Props) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: slipPage, loading, error } = useFetch<PagedResponse<ApiPayslip>>(API.payroll.myPayslips);
  const { data: me } = useFetch<ApiMe>(API.employees.me);
  const { data: settings } = useFetch<ApiPayrollSettings>(API.payroll.settings);
  const { data: taxDecl } = useFetch<ApiTaxDeclarationBrief>(API.payroll.myTaxDeclaration);
  const { data: fyConfig } = useFetch<ApiFinancialYearConfig>(API.settings.financialYear);

  const payslips = slipPage?.results ?? [];
  const slip = payslips.find(p => p.id === selectedId) ?? payslips[0] ?? null;

  if (loading) {
    return (
      <div className="empty-state">
        <i className="ti ti-loader-2 animate-spin text-2xl" />
        <div className="empty-state-desc mt-2">Loading your payslips…</div>
      </div>
    );
  }
  if (error) {
    return <div className="alert alert-error">Failed to load payslips. Please refresh.</div>;
  }
  if (!slip) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--on-bg)" }}>Payslips &amp; tax</h1>
          <p className="text-sm mt-1" style={{ color: "var(--on-variant)" }}>
            Understand your salary, deductions, taxes and employer contributions.
          </p>
        </div>
        <div className="empty-state">
          <div className="empty-state-icon">📄</div>
          <div className="empty-state-title">No payslips yet</div>
          <div className="empty-state-desc">Your payslips will appear here once payroll is processed for your account.</div>
        </div>
      </div>
    );
  }

  const gross = Number(slip.gross_earnings);
  const deductions = Number(slip.total_deductions);
  const net = Number(slip.net_pay);
  const paidDays = slip.total_working_days - Number(slip.lop_days);
  const bankMasked = me?.profile?.account_number ? `••••${me.profile.account_number.slice(-4)}` : "—";
  const gratuityRate = settings ? Number(settings.gratuity_rate) : null;

  const fyStart = currentFinancialYearStart(fyConfig?.financial_year_start_month ?? "April");
  const fyLabel = fyConfig?.current_financial_year ?? financialYearLabel(fyStart);
  const ytd = computeYtd(payslips, fyStart);

  return (
    <div className="flex flex-col gap-6">
      <PayslipHeader payslips={payslips} selectedId={selectedId} onSelect={setSelectedId} activeSlip={slip} />

      <PayslipHero
        slip={slip}
        bankName={me?.profile?.bank_name ?? null}
        bankMasked={bankMasked}
        pfNumber={me?.profile?.pf_number ?? null}
        gross={gross}
        deductions={deductions}
        paidDays={paidDays}
        totalDays={slip.total_working_days}
        net={net}
        payDateLabel={formatDate(slip.pay_date)}
      />

      <PayslipBreakdown slip={slip} gratuityRate={gratuityRate} />

      <div className="flex flex-col lg:flex-row gap-4 items-start">
        <div className="flex-1 min-w-0 flex flex-col gap-4">
          <PayslipYtdSummary monthRangeLabel={ytd.monthRangeLabel} ytdGross={ytd.gross} ytdNet={ytd.net} ytdIncomeTax={ytd.incomeTax} periodCount={ytd.periodCount} />
          <PayslipStatements payslips={payslips} currentFinancialYearLabel={fyLabel} />
        </div>
        <div className="w-full lg:w-72 shrink-0">
          <PayslipTaxNotice
            financialYearLabel={taxDecl?.financial_year ? `FY ${taxDecl.financial_year}` : fyLabel}
            fyEndLabel={fyEndLabel(fyStart)}
            isApproved={taxDecl?.status === "approved"}
            onNavigateToTax={onNavigateToTax ?? (() => router.push("/dashboard/ess"))}
          />
        </div>
      </div>

      <PayslipConfidentialNotice />
    </div>
  );
}
