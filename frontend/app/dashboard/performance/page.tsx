"use client";

import { useState } from "react";
import { usePermission } from "@/hooks/usePermission";
import PerformanceOverviewClient from "./_components/PerformanceOverviewClient";
import ManagerAppraisalWorkspace from "./_components/ManagerAppraisalWorkspace";
import PerformanceClient from "./_client";

export default function PerformancePage() {
  const canManageCycles = usePermission("performance.manage_cycles");
  const canReviewTeam = usePermission("performance.review_team");
  const [view, setView] = useState<"overview" | "detail">("overview");

  // HR / admins (performance.manage_cycles) keep the existing cycle-management
  // pages untouched. A Reporting Manager, who only reviews their own team, gets
  // the appraisal review workspace instead.
  if (!canManageCycles && canReviewTeam) return <ManagerAppraisalWorkspace />;

  if (view === "detail") {
    return <PerformanceClient onBack={() => setView("overview")} />;
  }
  return <PerformanceOverviewClient onOpen={() => setView("detail")} />;
}
