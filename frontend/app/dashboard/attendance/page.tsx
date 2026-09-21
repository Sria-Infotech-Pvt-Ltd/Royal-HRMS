"use client";

import { useEffect, useState } from "react";
import AttendanceOverviewClient from "./_components/AttendanceOverviewClient";
import AttendanceDetailClient from "./_components/AttendanceDetailClient";

export default function AttendancePage() {
  const [view, setView] = useState<"overview" | "detail">("overview");
  const [initialTab, setInitialTab] = useState<string | undefined>(undefined);

  // Deep link from Approvals' EmployeeAttendanceRow
  // (?view=employee&employee=...&month=...) still jumps straight into the
  // detail view — AttendanceDetailClient itself reads those same params to
  // pick the Employee Month View and the right employee/month.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("view") === "employee") setView("detail");
  }, []);

  if (view === "detail") {
    return <AttendanceDetailClient initialTab={initialTab} onBack={() => setView("overview")} />;
  }
  return (
    <AttendanceOverviewClient
      onOpen={tab => { setInitialTab(tab); setView("detail"); }}
    />
  );
}
