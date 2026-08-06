"use client";

import { useState } from "react";
import AttendanceTab from "./_components/AttendanceTab";
import AttendanceCorrectionsTab from "./_components/AttendanceCorrectionsTab";

type TabId = "attendance" | "corrections";

interface Props {
  initialTab?:  TabId;
  autoOpenNew?: boolean;
}

export default function MyAttendanceClient({ initialTab = "attendance", autoOpenNew = false }: Props) {
  const [tab, setTab] = useState<TabId>(initialTab);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">My Attendance</div>
          <div className="page-sub">View your personal attendance calendar and manage correction requests</div>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${tab === "attendance" ? " active" : ""}`} onClick={() => setTab("attendance")} suppressHydrationWarning>
          <i className="ti ti-calendar-stats" style={{ marginRight: 7 }} /> Attendance
        </button>
        <button className={`tab${tab === "corrections" ? " active" : ""}`} onClick={() => setTab("corrections")} suppressHydrationWarning>
          <i className="ti ti-clock-edit" style={{ marginRight: 7 }} /> Attendance Corrections
        </button>
      </div>

      {tab === "attendance"  && <AttendanceTab />}
      {tab === "corrections" && <AttendanceCorrectionsTab autoOpenNew={autoOpenNew} />}
    </div>
  );
}
