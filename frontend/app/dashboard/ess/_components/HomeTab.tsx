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
  return target.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
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
      icon: "ti-clock-check", label: "ATTENDANCE",
      value: attStats ? `${attStats.days_present}/${attStats.working_days}` : "—",
      sub: "days present this month", linkText: "View details",
      onClick: () => onNavigate("attendance"),
    },
    {
      icon: "ti-beach", label: "LEAVE BALANCE",
      value: balances ? leaveBalanceTotal.toFixed(1) : "—",
      sub: "days available", linkText: "View details",
      onClick: () => onNavigate("leave"),
    },
    {
      icon: "ti-calendar-event", label: "NEXT PAYDAY",
      value: payrollSettings ? nextPayday(payrollSettings.pay_day) : "—",
      sub: latestPayslip ? "payslip follows approval" : "no payslips yet", linkText: "View details",
      onClick: () => onNavigate("payslips"),
    },
    {
      icon: "ti-list-check", label: "MY REQUESTS",
      value: String(openRequestCount),
      sub: "open and recent requests", linkText: "View all",
      onClick: () => onNavigate("requests"),
    },
  ];

  const primaryActions = [
    { icon: "ti-beach",       title: "Request leave",            sub: "Check balance and submit dates",       onClick: () => onNavigate("leave") },
    { icon: "ti-clock-edit",  title: "Regularize attendance",     sub: "Correct a missing or late punch",      onClick: () => onNavigate("attendance") },
    { icon: "ti-receipt",     title: "Download payslip",          sub: "Monthly salary statements",            onClick: () => onNavigate("payslips") },
    { icon: "ti-user-circle", title: "View my full profile",      sub: "Personal, bank and emergency details", onClick: () => onNavigate("profile") },
    { icon: "ti-folder",      title: "Upload document",           sub: "Add a document to your profile",       onClick: () => onNavigate("documents") },
    { icon: "ti-headset",     title: "Ask HR",                    sub: "Raise and track a support request",    onClick: () => onNavigate("hrHelp") },
  ];

  const secondaryActions = [
    { icon: "ti-wallet",         title: "Claim an expense",   sub: "Submit a reimbursement claim",        onClick: () => onNavigate("expenses") },
    { icon: "ti-file-text",      title: "Complete appraisal", sub: "Finish your review for this cycle",   onClick: () => onNavigate("appraisals") },
    { icon: "ti-shield-check",   title: "Read policies",      sub: "Company policies and shared assets",  onClick: () => onNavigate("assets") },
  ];

  return (
    <div>
      <HomeStatTiles tiles={tiles} />

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, alignItems: "start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 20, minWidth: 0 }}>
          <HomeQuickActions primary={primaryActions} secondary={secondaryActions} />
          <HomeRequestsList items={requestItems.slice(0, 5)} onViewAll={() => onNavigate("requests")} />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20, minWidth: 0 }}>
          <HomeTodayPanel status={status} stats={attStats} />
          <HomePayslipsPanel
            payslips={payslips?.results ?? []}
            onViewAll={() => onNavigate("payslips")}
            onOpenDocuments={() => onNavigate("documents")}
          />
        </div>
      </div>
    </div>
  );
}
