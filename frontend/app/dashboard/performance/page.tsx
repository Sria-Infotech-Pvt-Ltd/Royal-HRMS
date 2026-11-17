"use client";

import { usePermission } from "@/hooks/usePermission";
import PerformanceHub from "./_components/PerformanceHub";
import ManagerAppraisalWorkspace from "./_components/ManagerAppraisalWorkspace";

export default function PerformancePage() {
  const canManageCycles = usePermission("performance.manage_cycles");
  const canReviewTeam = usePermission("performance.review_team");

  // HR / admins (performance.manage_cycles) get the full hub: overview, review queue and cycles. A Reporting Manager, who only
  // reviews their own team, gets the appraisal review workspace instead.
  if (!canManageCycles && canReviewTeam) return <ManagerAppraisalWorkspace />;
  return <PerformanceHub />;
}
