"use client";

import { useState } from "react";
import AttendanceTab from "./_components/AttendanceTab";
import AttendanceCorrectionsTab from "./_components/AttendanceCorrectionsTab";
import WeeklyTimesheetCard from "../ess/_components/WeeklyTimesheetCard";

interface Props {
  autoOpenNew?: boolean;
}

// One continuous page (stat cards, calendar, weekly timesheet, then
// attendance requests) — not the old Attendance/Corrections sub-tab split,
// which the reference layout doesn't show at all. "Regularize attendance"
// in the header opens the same real correction request modal
// AttendanceCorrectionsTab's own "Request Attendance Correction" quick
// action does, just reachable from the top of the page too.
export default function MyAttendanceClient({ autoOpenNew = false }: Props) {
  const [openCorrectionKey, setOpenCorrectionKey] = useState(0);
  const [pendingAutoOpen, setPendingAutoOpen] = useState(autoOpenNew);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Attendance</div>
          <div className="page-sub">Punch status, monthly calendar and regularization requests.</div>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-filled"
            onClick={() => { setPendingAutoOpen(true); setOpenCorrectionKey(k => k + 1); }}
            suppressHydrationWarning
          >
            Regularize attendance
          </button>
        </div>
      </div>

      <AttendanceTab />

      <div className="mb-16" />
      <WeeklyTimesheetCard />

      <div className="mb-16" />
      <AttendanceCorrectionsTab
        key={openCorrectionKey}
        autoOpenNew={pendingAutoOpen}
      />
    </div>
  );
}
