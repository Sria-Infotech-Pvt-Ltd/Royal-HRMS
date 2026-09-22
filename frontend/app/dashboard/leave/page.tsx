"use client";

// Lands directly on the real Leave tabs — no marketing-style landing screen.
import { useEffect, useState } from "react";
import LeavePageClient from "./_client";

type DetailTab = "dashboard" | "apply" | "calendar" | "analytics";

export default function LeavePage() {
  // Deep links (e.g. Reports' "leave-analytics" tile, ManagerDashboard's
  // "apply_leave" action item) still land straight on the intended tab.
  const [initialTab, setInitialTab] = useState<DetailTab>("dashboard");

  useEffect(() => {
    const tab = new URLSearchParams(window.location.search).get("tab");
    if (tab === "apply" || tab === "calendar" || tab === "analytics") setInitialTab(tab);
  }, []);

  return <LeavePageClient initialTab={initialTab} />;
}
