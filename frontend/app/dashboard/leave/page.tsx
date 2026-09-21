"use client";

import { useEffect, useState } from "react";
import LeaveOverviewClient from "./_components/LeaveOverviewClient";
import LeavePageClient from "./_client";

type DetailTab = "dashboard" | "apply" | "calendar" | "analytics";

export default function LeavePage() {
  // Deep links (e.g. Reports' "leave-analytics" tile, ManagerDashboard's
  // "apply_leave" action item) still land straight on the intended tab
  // instead of the new overview landing.
  const [view, setView] = useState<"overview" | "detail">("overview");
  const [initialTab, setInitialTab] = useState<DetailTab>("dashboard");

  useEffect(() => {
    const tab = new URLSearchParams(window.location.search).get("tab");
    if (tab === "apply" || tab === "calendar" || tab === "analytics") {
      setInitialTab(tab);
      setView("detail");
    }
  }, []);

  if (view === "detail") {
    return <LeavePageClient initialTab={initialTab} onBack={() => setView("overview")} />;
  }
  return (
    <LeaveOverviewClient
      onOpen={tab => {
        setInitialTab(tab === "apply" || tab === "calendar" || tab === "analytics" ? tab : "dashboard");
        setView("detail");
      }}
    />
  );
}
