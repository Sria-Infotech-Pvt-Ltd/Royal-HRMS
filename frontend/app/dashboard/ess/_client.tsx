"use client";

import { useState } from "react";
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
import ProfileClient from "../profile/ProfileClient";
import ProfileSummaryTab from "./_components/ProfileSummaryTab";
import MyAttendanceClient from "../my-attendance/_client";
import LeavePageClient from "../leave/_client";
import MyPayslipPage from "../my-payslip/page";
import DocumentCenterPage from "../documents/page";
import SeparationPage from "../separation/page";
import MyRequestsClient from "../my-requests/_client";

type TabId = "home" | "profile" | "attendance" | "leave" | "payslips" | "tax" | "expenses" | "documents" | "growth" | "appraisals" | "assets" | "employment" | "requests" | "hrHelp";

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: "home",        label: "Home",         icon: "ti-home" },
  { id: "profile",     label: "My Profile",   icon: "ti-user-circle" },
  { id: "attendance",  label: "Attendance",   icon: "ti-clock-check" },
  { id: "leave",       label: "Leave",        icon: "ti-beach" },
  { id: "payslips",    label: "Payslips",     icon: "ti-receipt" },
  { id: "tax",         label: "Tax",          icon: "ti-file-invoice" },
  { id: "expenses",    label: "Expenses",     icon: "ti-wallet" },
  { id: "documents",   label: "Documents",    icon: "ti-folder" },
  { id: "growth",      label: "Growth",       icon: "ti-target-arrow" },
  { id: "appraisals",  label: "Appraisals",   icon: "ti-file-text" },
  { id: "assets",      label: "Policies & Assets", icon: "ti-device-laptop" },
  { id: "employment",  label: "Employment",   icon: "ti-logout" },
  { id: "requests",    label: "Requests",     icon: "ti-list-check" },
  { id: "hrHelp",      label: "HR Help",      icon: "ti-headset" },
];

export default function EssShellClient({ session }: { session: SessionPayload }) {
  const [tab, setTab] = useState<TabId>("home");
  const [fullProfile, setFullProfile] = useState(false);
  const { data: status, refetch: refetchStatus } = useAttendanceStatus();

  return (
    <div>
      <HomeBanner status={status} onPunchSuccess={refetchStatus} />

      <div className="ess-tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`ess-tab${tab === t.id ? " active" : ""}`}
            onClick={() => { setTab(t.id); if (t.id === "profile") setFullProfile(false); }}
            suppressHydrationWarning
          >
            <i className={`ti ${t.icon}`} style={{ marginRight: 5 }} /> {t.label}
          </button>
        ))}
      </div>

      {tab === "home"       && <HomeTab onNavigate={setTab} status={status} />}
      {tab === "profile" && (
        fullProfile
          ? (
            <div>
              <button
                onClick={() => setFullProfile(false)}
                style={{ display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", color: "var(--primary)", fontSize: 12.5, fontWeight: 700, cursor: "pointer", padding: 0, marginBottom: 12 }}
              >
                <i className="ti ti-arrow-left" /> Back to profile summary
              </button>
              <ProfileClient session={session} />
            </div>
          )
          : <ProfileSummaryTab onOpenFullProfile={() => setFullProfile(true)} />
      )}
      {tab === "attendance" && <MyAttendanceClient />}
      {tab === "leave"      && <LeavePageClient />}
      {tab === "payslips"   && <MyPayslipPage />}
      {tab === "tax"        && <TaxTab />}
      {tab === "expenses"   && <ExpensesTab />}
      {tab === "documents"  && <DocumentCenterPage />}
      {tab === "growth"     && <GrowthTab />}
      {tab === "appraisals" && <AppraisalsTab />}
      {tab === "assets"     && <PoliciesAssetsTab onNavigateToDocuments={() => setTab("documents")} />}
      {tab === "employment" && <SeparationPage />}
      {tab === "requests"   && <MyRequestsClient initialTab="all" />}
      {tab === "hrHelp"     && <HrHelpTab />}
    </div>
  );
}
