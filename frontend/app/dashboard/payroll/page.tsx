"use client";

import { useState } from "react";
import PayrollOverviewClient from "./_components/PayrollOverviewClient";
import PayrollDetailClient from "./_components/PayrollDetailClient";

type TabId = "dashboard" | "salary_setup" | "adjustments" | "reports" | "analytics";

export default function PayrollPage() {
  const [view, setView] = useState<"overview" | "detail">("overview");
  const [initialTab, setInitialTab] = useState<TabId | undefined>(undefined);

  if (view === "detail") {
    return <PayrollDetailClient initialTab={initialTab} onBack={() => setView("overview")} />;
  }
  return (
    <PayrollOverviewClient
      onOpen={tab => {
        setInitialTab(tab as TabId | undefined);
        setView("detail");
      }}
    />
  );
}
