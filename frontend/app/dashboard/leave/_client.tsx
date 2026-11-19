"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import LeaveDashboard, { LeaveBalanceStats } from "./_components/LeaveDashboard";
import ApplyLeaveForm from "./_components/ApplyLeaveForm";
import TeamCalendar   from "./_components/TeamCalendar";
import LeaveAnalytics from "./_components/LeaveAnalytics";
import UpcomingHolidaysCard from "./_components/UpcomingHolidaysCard";
import TeamCoverageCard from "./_components/TeamCoverageCard";
import LeavePolicyGuidanceCard from "./_components/LeavePolicyGuidanceCard";
import { LeaveStyles } from "./_components/leaveStyles";
import { tr } from "@/lib/i18n/tr";

type DetailTab = "dashboard" | "apply" | "calendar" | "analytics";

interface Props {
  onBack?:     () => void;
  // Deep links (Reports' "leave-analytics" tile, ManagerDashboard's
  // "apply_leave" action item, page.tsx's own ?tab= query) still land
  // straight on the intended surface — now opened as a modal on top of the
  // one continuous page instead of switching to a different sub-tab.
  initialTab?: DetailTab;
}

// One continuous page (balances, requests, holidays, team coverage, policy
// guidance) — matching the reference layout, which never shows the old
// Dashboard/Apply Leave/Team Calendar/Analytics sub-tab bar. "Request leave"
// opens the same real Apply Leave form as before, now in a modal instead of
// a tab switch; Team Calendar and Analytics stay fully reachable (their real
// fetches and functionality are unchanged) via modals opened from this page
// rather than being gated behind tabs.
export default function LeavePageClient({ onBack, initialTab = "dashboard" }: Props) {
  const [showApply,    setShowApply]    = useState(initialTab === "apply");
  const [showCalendar, setShowCalendar] = useState(initialTab === "calendar");
  const [showAnalytics, setShowAnalytics] = useState(initialTab === "analytics");

  return (
    <div>
      <LeaveStyles />
      <div className="page-header">
        <div>
          {onBack && (
            <button
              onClick={onBack}
              style={{ display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", color: "var(--primary)", fontSize: 12.5, fontWeight: 700, cursor: "pointer", padding: 0, marginBottom: 8 }}
            >
              <i className="ti ti-arrow-left" /> {tr("Back to overview")}
            </button>
          )}
          <div className="page-title">{tr("Leave")}</div>
          <div className="page-sub">{tr("Balances, requests, holidays and team coverage.")}</div>
        </div>
        <div className="page-actions lv-actions">
          <button className="btn btn-ghost" onClick={() => setShowCalendar(true)}>
            <i className="ti ti-calendar-event" /> {tr("Team calendar")}
          </button>
          <button className="btn btn-ghost" onClick={() => setShowAnalytics(true)}>
            <i className="ti ti-chart-bar" /> {tr("Analytics")}
          </button>
          <button className="btn btn-filled" onClick={() => setShowApply(true)} suppressHydrationWarning>
            {tr("Request leave")}
          </button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <LeaveBalanceStats />
        <div className="leave-pair">
          <LeaveDashboard />
          <UpcomingHolidaysCard />
        </div>
        <div className="leave-pair">
          <TeamCoverageCard />
          <LeavePolicyGuidanceCard />
        </div>
      </div>

      {showApply && (
        <Modal
          title={
            <div>
              <div className="text-[18px] font-bold">{tr("Leave request")}</div>
              <div className="mt-0.5 text-[12px] font-normal text-[var(--on-variant)]">
                {tr("Complete the required information. Your submission will appear in My Requests.")}
              </div>
            </div>
          }
          onClose={() => setShowApply(false)}
          size="lg"
          maxWidth={820}
          bodyStyle={{ padding: 0 }}
        >
          <ApplyLeaveForm onCancel={() => setShowApply(false)} />
        </Modal>
      )}

      {showCalendar && (
        <Modal title={tr("Team calendar")} onClose={() => setShowCalendar(false)} size="lg">
          <TeamCalendar />
        </Modal>
      )}

      {showAnalytics && (
        <Modal title={tr("Leave analytics")} onClose={() => setShowAnalytics(false)} size="lg">
          <LeaveAnalytics />
        </Modal>
      )}
    </div>
  );
}
