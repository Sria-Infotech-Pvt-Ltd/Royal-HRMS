"use client";

// Employee Self Service shell — the reference's .ess-shell: a sticky hero
// (greeting + Punch in/out) over the pill tab bar, then the active page.
// Every tab keeps its real, endpoint-backed content; only the chrome here is
// the reference's. `session` is accepted for backward compatibility with the
// server component that renders this shell but is no longer used directly.

import { useState, useEffect } from "react";
import { setViewAsEmployee } from "@/lib/viewAs";
import ViewAsStrip from "./_components/ViewAsStrip";
import type { SessionPayload } from "@/lib/session";
import { useAttendanceStatus } from "@/hooks/useEmployeeDashboard";
import HomeBanner from "./_components/HomeBanner";
import HomeTab from "./_components/HomeTab";
import PoliciesAssetsTab from "./_components/PoliciesAssetsTab";
import HrHelpTab from "./_components/HrHelpTab";
import TaxTab from "./_components/TaxTab";
import ExpensesTab from "./_components/ExpensesTab";
import GrowthTab from "./_components/GrowthTab";
import AppraisalsTab from "./_components/AppraisalsTab";
import ProfileSummaryTab from "./_components/ProfileSummaryTab";
import EssAttendanceTab from "./_components/EssAttendanceTab";
import LeavePageClient from "../leave/_client";
import EssPayslipsTab from "./_components/EssPayslipsTab";
import MyDocumentsTab from "./_components/MyDocumentsTab";
import EmploymentTab from "./_components/EmploymentTab";
import EssRequestsTab from "./_components/EssRequestsTab";

type TabId = "home" | "profile" | "attendance" | "leave" | "payslips" | "tax" | "expenses" | "documents" | "growth" | "appraisals" | "assets" | "employment" | "requests" | "hrHelp";

// Labels exactly as the reference's tab bar spells them.
const TABS: { id: TabId; label: string }[] = [
  { id: "home",        label: "Home" },
  { id: "profile",     label: "My profile" },
  { id: "attendance",  label: "Attendance" },
  { id: "leave",       label: "Leave" },
  { id: "payslips",    label: "Payslips" },
  { id: "tax",         label: "Tax" },
  { id: "expenses",    label: "Expenses" },
  { id: "documents",   label: "Documents" },
  { id: "growth",      label: "Growth" },
  { id: "appraisals",  label: "Appraisals" },
  { id: "assets",      label: "Policies & assets" },
  { id: "employment",  label: "Employment" },
  { id: "requests",    label: "Requests" },
  { id: "hrHelp",      label: "HR help" },
];

const TAB_IDS = new Set<string>(TABS.map(t => t.id));

export default function EssShellClient({ session: _session, viewAsEmployee }: { session: SessionPayload; viewAsEmployee?: string }) {
  const [tab, setTab] = useState<TabId>("home");
  // Set while rendering, before any child fetches: effects run children-first, so an effect here would be too late.
  // Only in the browser — module state on the server would be shared between requests.
  if (typeof window !== "undefined") setViewAsEmployee(viewAsEmployee ?? null);
  // Re-set in an effect too (development runs effects twice, which would otherwise clear it), and cleared on leaving
  // so no other page keeps asking as this employee.
  useEffect(() => {
    setViewAsEmployee(viewAsEmployee ?? null);
    return () => setViewAsEmployee(null);
  }, [viewAsEmployee]);
  const { data: status, refetch: refetchStatus } = useAttendanceStatus();

  // Deep links (e.g. the top-nav avatar chip's "?tab=profile") land straight
  // on the intended tab instead of always resetting to Home.
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("tab");
    if (requested && TAB_IDS.has(requested)) setTab(requested as TabId);
  }, []);

  return (
    <div className="ess-shell">
      <div className="ess-sticky">
        {viewAsEmployee && <ViewAsStrip />}
        <HomeBanner status={status} onPunchSuccess={refetchStatus} isReadOnly={!!viewAsEmployee} />
        <nav className="ess-tabs" aria-label="Employee Self Service">
          {TABS.map(t => (
            <button
              key={t.id}
              type="button"
              className={`ess-tab${tab === t.id ? " on" : ""}`}
              onClick={() => setTab(t.id)}
              suppressHydrationWarning
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "home"       && <HomeTab onNavigate={setTab} status={status} />}
      {tab === "profile"    && <ProfileSummaryTab />}
      {tab === "attendance" && <EssAttendanceTab />}
      {tab === "leave"      && <LeavePageClient />}
      {tab === "payslips"   && <EssPayslipsTab onNavigateToTax={() => setTab("tax")} />}
      {tab === "tax"        && <TaxTab onNavigateToDocuments={() => setTab("documents")} />}
      {tab === "expenses"   && <ExpensesTab />}
      {tab === "documents"  && <MyDocumentsTab />}
      {tab === "growth"     && <GrowthTab onNavigateToAppraisals={() => setTab("appraisals")} />}
      {tab === "appraisals" && <AppraisalsTab />}
      {tab === "assets"     && <PoliciesAssetsTab />}
      {tab === "employment" && <EmploymentTab onNavigateToDocuments={() => setTab("documents")} />}
      {tab === "requests"   && <EssRequestsTab />}
      {tab === "hrHelp"     && <HrHelpTab />}

      <div className="ess-footer-note">
        {viewAsEmployee
          ? "You are viewing this workspace read-only. Nothing you do here is saved."
          : "Requests are recorded against your employee record and routed to the approver shown on each one."}
      </div>
    </div>
  );
}
