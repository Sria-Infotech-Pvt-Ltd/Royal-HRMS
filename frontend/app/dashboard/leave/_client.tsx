"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import LeaveDashboard from "./_components/LeaveDashboard";
import ApplyLeaveForm from "./_components/ApplyLeaveForm";
import TeamCalendar   from "./_components/TeamCalendar";
import LeaveAnalytics from "./_components/LeaveAnalytics";
import UpcomingHolidaysCard from "./_components/UpcomingHolidaysCard";
import TeamCoverageCard from "./_components/TeamCoverageCard";
import LeavePolicyGuidanceCard from "./_components/LeavePolicyGuidanceCard";

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
      <div className="page-header">
        <div>
          {onBack && (
            <button
              onClick={onBack}
              style={{ display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", color: "var(--primary)", fontSize: 12.5, fontWeight: 700, cursor: "pointer", padding: 0, marginBottom: 8 }}
            >
              <i className="ti ti-arrow-left" /> Back to overview
            </button>
          )}
          <div className="page-title">Leave</div>
          <div className="page-sub">Balances, requests, holidays and team coverage.</div>
        </div>
        <div className="page-actions" style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-ghost" onClick={() => setShowAnalytics(true)} suppressHydrationWarning>
            <i className="ti ti-chart-bar" /> Analytics
          </button>
          <button className="btn btn-filled" onClick={() => setShowApply(true)} suppressHydrationWarning>
            Request leave
          </button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <LeaveDashboard
          onApply={() => setShowApply(true)}
          onViewCalendar={() => setShowCalendar(true)}
        />
        <UpcomingHolidaysCard />
        <TeamCoverageCard onOpenFullCalendar={() => setShowCalendar(true)} />
        <LeavePolicyGuidanceCard />
      </div>

      {showApply && (
        <Modal title="Request leave" onClose={() => setShowApply(false)} size="lg" bodyStyle={{ padding: 0 }}>
          <ApplyLeaveForm onCancel={() => setShowApply(false)} />
        </Modal>
      )}

      {showCalendar && (
        <Modal title="Team calendar" onClose={() => setShowCalendar(false)} size="lg">
          <TeamCalendar />
        </Modal>
      )}

      {showAnalytics && (
        <Modal title="Leave analytics" onClose={() => setShowAnalytics(false)} size="lg">
          <LeaveAnalytics />
        </Modal>
      )}
    </div>
  );
}
