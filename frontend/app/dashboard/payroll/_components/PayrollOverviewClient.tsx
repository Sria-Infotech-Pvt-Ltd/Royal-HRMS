"use client";

import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import {
  KpiTile, OverviewRow, QuickActionTile, WeeklyBarChart, BrandBanner,
  CapabilityGrid, OperationalToolsGrid, PlatformSafeguards,
} from "@/components/dashboard/ModuleOverviewKit";

interface OverviewRowData { name: string; context: string; status_label: string; status_kind: "success" | "error" | "warn"; link: string }
interface OverviewData {
  gross_pay: number; deductions: number; net_pay: number; blocked: number; employee_count: number;
  cycle_label: string; cycle_status_display: string; salary_revisions_this_month: number;
  overview_rows: OverviewRowData[]; weekly_chart: { label: string; count: number }[];
}

const CAPABILITIES = [
  { title: "Payroll periods", desc: "Draft, validate, approve, lock and publish controlled cycles.", href: "/dashboard/payroll" },
  { title: "Compensation history", desc: "Effective-dated salary, allowances, revisions and arrears.", href: "/dashboard/payroll?tab=salary_setup" },
  { title: "Inputs", desc: "Attendance, leave, overtime, variable pay, reimbursements and loans.", href: "/dashboard/payroll?tab=adjustments" },
  { title: "Statutory processing", desc: "PF, ESI, professional tax, LWF and tax configuration.", href: "/dashboard/settings/payroll-config" },
  { title: "Exceptions", desc: "Master-data, bank, negative-net and variance blockers.", href: "/dashboard/employees" },
  { title: "Final settlement", desc: "Notice recovery, leave encashment, gratuity and exit deductions.", href: "/dashboard/separation" },
  { title: "Outputs", desc: "Bank advice, accounting journal, payslips and statutory registers.", href: "/dashboard/payroll?tab=reports" },
  { title: "Reconciliation", desc: "Prior-period variance, finance totals and payment confirmation.", href: "/dashboard/payroll?tab=analytics" },
];

const OPERATIONAL_TOOLS = [
  { title: "Run pre-payroll checks", desc: "Validate all employee and period inputs.", href: "/dashboard/payroll" },
  { title: "Process draft payroll", desc: "Calculate earnings, deductions and net pay.", href: "/dashboard/payroll" },
  { title: "Review variances", desc: "Compare employee and cost-center changes.", href: "/dashboard/payroll?tab=analytics" },
  { title: "Approve payroll", desc: "Capture dual control before bank output.", href: "/dashboard/payroll" },
  { title: "Final settlement", desc: "Calculate and approve an exiting employee.", href: "/dashboard/separation" },
  { title: "Publish payslips", desc: "Release approved statements to employees.", href: "/dashboard/payroll?tab=reports" },
];

const INR = (n: number) => n >= 100000 ? `₹${(n / 100000).toFixed(1)}L` : `₹${Math.round(n).toLocaleString("en-IN")}`;

export default function PayrollOverviewClient({ onOpen }: { onOpen: (tab?: string) => void }) {
  const router = useRouter();
  const { data } = useFetch<OverviewData>(API.dashboard.payrollOverview);

  function go(href: string) {
    if (href.startsWith("/dashboard/payroll")) {
      const tab = new URL(href, "http://x").searchParams.get("tab") ?? undefined;
      onOpen(tab);
    } else {
      router.push(href);
    }
  }

  return (
    <div>
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>Dashboard / Payroll</div>
      <div className="pagehead">
        <div>
          <h1>{data?.cycle_label ?? "—"} <em>payroll</em></h1>
          <p className="lede">
            Validate employee records, attendance inputs and statutory deductions before processing payroll.
          </p>
        </div>
        <button className="btn btn-filled" onClick={() => onOpen()}>Run payroll checks</button>
      </div>

      <div className="stats">
        <KpiTile label="GROSS PAY" value={data ? INR(data.gross_pay) : "—"} sub={data ? `${data.employee_count} employees` : ""} tone="brand" />
        <KpiTile label="DEDUCTIONS" value={data ? INR(data.deductions) : "—"} sub="PF · ESI · TDS" tone="warn" />
        <KpiTile label="NET PAY" value={data ? INR(data.net_pay) : "—"} sub="Estimated" tone="ok" />
        <KpiTile label="BLOCKED" value={data?.blocked ?? "—"} sub="Records need action" tone="crit" />
      </div>

      <div className="module-grid">
        <div className="module-card">
          <div className="mc-head">
            <div className="mc-title">Payroll overview</div>
            <div className="mc-sub">Current records and items requiring attention.</div>
          </div>
          <div style={{ padding: "0 20px 4px" }}>
            {!data || data.overview_rows.length === 0 ? (
              <div className="empty-state"><i className="ti ti-currency-rupee" /><h3>No cycle yet</h3></div>
            ) : data.overview_rows.map((row, i) => (
              <OverviewRow key={i} label={row.name} sub={row.context} chip={row.status_label} chipTone={row.status_kind} onOpen={() => go(row.link)} />
            ))}
          </div>
        </div>

        <div className="module-card">
          <div className="mc-head">
            <div className="mc-title">Quick actions</div>
            <div className="mc-sub">Common tasks for your current role.</div>
          </div>
          <div className="quick-grid">
            <QuickActionTile title="Payroll run" sub={data ? `${data.cycle_label}${data.cycle_status_display ? ` ${data.cycle_status_display.toLowerCase()}` : ""}` : ""} onClick={() => onOpen()} />
            <QuickActionTile title="Salary revisions" sub={data ? `${data.salary_revisions_this_month} effective this month` : "Setup and effective dates"} onClick={() => onOpen("salary_setup")} />
            <QuickActionTile title="Statutory returns" sub="PF · ESI · Professional tax" onClick={() => router.push("/dashboard/settings/payroll-config")} />
            <QuickActionTile title="Payslips" sub="Publish after approval" onClick={() => onOpen("reports")} />
          </div>
          <WeeklyBarChart data={data?.weekly_chart ?? []} />
        </div>
      </div>

      <BrandBanner />
      <CapabilityGrid title="Complete capability coverage" sub="Lifecycle functions designed for multi-year HR operations." items={CAPABILITIES} onOpen={go} />
      <OperationalToolsGrid title="Operational tools" sub="Role-aware tools with effective dates, approval states and audit events." items={OPERATIONAL_TOOLS} onLaunch={go} />
      <PlatformSafeguards />
    </div>
  );
}
