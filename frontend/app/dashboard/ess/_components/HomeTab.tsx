"use client";

// Landing summary for My Workspace — greeting banner, 4 stat tiles, quick
// actions, a "Today" panel, a "My requests" preview and a "Payslips &
// documents" preview. No new endpoints: every number here comes from APIs
// the individual tabs already call — useAttendanceStatus/attendance stats,
// leave balances, my payslips, and the same 4 "my requests" endpoints
// my-requests/_client.tsx aggregates (via the same _data.ts normalisers, so
// there's exactly one place that turns a leave/expense/correction/wfh row
// into a MyRequestItem, not two).

import { useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AttendanceStats } from "@/types/attendance";
import type { AttendanceStatus } from "@/types/employeeDashboard";
import type { PayrollSettings } from "@/types/payroll";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import { LeaveRequest } from "../../leave/_data";
import type { Expense } from "../../expenses/_components/ExpenseClaims";
import {
  MyCorrectionRequest, PaginatedResponse,
  correctionToMyItem, expenseToMyItem, leaveToMyItem, toSortableTime, wfhToMyItem,
} from "../../my-requests/_data";
import HomeStatTiles from "./HomeStatTiles";
import HomeQuickActions from "./HomeQuickActions";
import HomeTodayPanel from "./HomeTodayPanel";
import HomeRequestsList from "./HomeRequestsList";
import HomePayslipsPanel from "./HomePayslipsPanel";

interface ApiPayslip {
  cycle:       string;
  pay_date:    string;
  net_pay:     string;
  status:      string;
  payslip_pdf: string | null;
}

function todayMonthYear() {
  const now = new Date();
  return { month: now.getMonth() + 1, year: now.getFullYear() };
}

/** Next payday from the org's payroll cycle config (real DB-backed value —
 *  same `pay_day` field PayrollDashboard.tsx uses), not a hardcoded date. */
function nextPayday(payDay: number | undefined): string {
  if (!payDay) return "—";
  const now = new Date();
  const target = now.getDate() <= payDay
    ? new Date(now.getFullYear(), now.getMonth(), payDay)
    : new Date(now.getFullYear(), now.getMonth() + 1, payDay);
  return target.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export type EssTabId =
  | "profile" | "attendance" | "leave" | "payslips" | "tax" | "expenses"
  | "documents" | "assets" | "growth" | "appraisals" | "employment" | "requests" | "hrHelp";

interface Props {
  onNavigate: (tab: EssTabId) => void;
  status: AttendanceStatus | null;
}

export default function HomeTab({ onNavigate, status }: Props) {
  const { month, year } = todayMonthYear();

  const { data: attStats } = useFetch<AttendanceStats>(`${API.attendance.stats}?month=${month}&year=${year}`);
  const { data: balances } = useFetch<{ available_days: number }[]>(`${API.leave.balance}?year=${year}`);
  const { data: payslips }   = useFetch<PaginatedResponse<ApiPayslip>>(API.payroll.myPayslips);
  const { data: payrollSettings } = useFetch<PayrollSettings>(API.payroll.settings);

  const { data: leaveRaw }      = useFetch<PaginatedResponse<LeaveRequest>>(`${API.leave.requests}?page_size=100`);
  const { data: expenseRaw }    = useFetch<PaginatedResponse<Expense>>(`${API.expenses.list}?page_size=100`);
  const { data: correctionRaw } = useFetch<PaginatedResponse<MyCorrectionRequest>>(`${API.attendance.myCorrections}?page_size=100`);
  const { data: wfhRaw }        = useFetch<PaginatedResponse<WorkFromHomeRequest>>(`${API.workFromHome.requests}?page_size=100`);

  const requestItems = useMemo(() => {
    const all = [
      ...(leaveRaw?.results ?? []).map(leaveToMyItem),
      ...(expenseRaw?.results ?? []).map(expenseToMyItem),
      ...(correctionRaw?.results ?? []).map(correctionToMyItem),
      ...(wfhRaw?.results ?? []).map(wfhToMyItem),
    ];
    return all.sort((a, b) => toSortableTime(b.submittedAt) - toSortableTime(a.submittedAt));
  }, [leaveRaw, expenseRaw, correctionRaw, wfhRaw]);

  const openRequestCount = useMemo(
    () => requestItems.filter(r => r.displayStatus === "pending").length,
    [requestItems],
  );

  const leaveBalanceTotal = useMemo(
    () => (balances ?? []).reduce((sum, b) => sum + (Number(b.available_days) || 0), 0),
    [balances],
  );

  const latestPayslip = payslips?.results?.[0];

  const tiles = [
    {
      label: "ATTENDANCE",
      value: attStats ? `${attStats.days_present}/${attStats.working_days}` : "—",
      sub: "days present this month", linkText: "View details",
      onClick: () => onNavigate("attendance"),
    },
    {
      label: "LEAVE BALANCE",
      value: balances ? leaveBalanceTotal.toFixed(1) : "—",
      sub: "days available", linkText: "View details",
      onClick: () => onNavigate("leave"),
    },
    {
      label: "NEXT PAYDAY",
      value: payrollSettings ? nextPayday(payrollSettings.pay_day) : "—",
      sub: latestPayslip ? "payslip follows approval" : "no payslips yet", linkText: "View details",
      onClick: () => onNavigate("payslips"),
    },
    {
      label: "MY REQUESTS",
      value: String(openRequestCount),
      sub: "open and recent requests", linkText: "View all",
      onClick: () => onNavigate("requests"),
    },
  ];

  const actions = [
    { glyph: "＋", title: "Request leave",         sub: "Check balance and submit dates",              onClick: () => onNavigate("leave") },
    { glyph: "✓",  title: "Regularize attendance", sub: "Correct a missing or late punch",             onClick: () => onNavigate("attendance") },
    { glyph: "₹",  title: "Download payslip",      sub: "View monthly salary statements",              onClick: () => onNavigate("payslips") },
    { glyph: "⌁",  title: "View my full profile",  sub: "Open the same employee record used by Admin", onClick: () => onNavigate("profile") },
    { glyph: "⇧",  title: "Upload document",       sub: "Submit declarations or certificates",         onClick: () => onNavigate("documents") },
    { glyph: "?",  title: "Ask HR",                sub: "Raise and track a support request",           onClick: () => onNavigate("hrHelp") },
    { glyph: "₹",  title: "Claim an expense",      sub: "Submit a work expense for approval",          onClick: () => onNavigate("expenses") },
    { glyph: "✦",  title: "Complete appraisal",    sub: "Self-review, outcome and development plan",   onClick: () => onNavigate("appraisals") },
    { glyph: "▣",  title: "Read policies",         sub: "Company guidance and assigned assets",        onClick: () => onNavigate("assets") },
  ];

  return (
    <section className="ess-page">
      <HomeStatTiles tiles={tiles} />

      <div className="ess-grid">
        <HomeQuickActions actions={actions} />
        <HomeTodayPanel status={status} onNavigate={onNavigate} />
      </div>

      <div className="ess-grid">
        <HomeRequestsList items={requestItems.slice(0, 3)} onViewAll={() => onNavigate("requests")} />
        <HomePayslipsPanel
          payslips={payslips?.results ?? []}
          onViewAll={() => onNavigate("payslips")}
          onNavigate={onNavigate}
        />
      </div>
    </section>
  );
}
