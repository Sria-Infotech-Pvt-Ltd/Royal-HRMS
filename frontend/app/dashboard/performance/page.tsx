"use client";

import { useState } from "react";
import PerformanceOverviewClient from "./_components/PerformanceOverviewClient";
import PerformanceClient from "./_client";

export default function PerformancePage() {
  const [view, setView] = useState<"overview" | "detail">("overview");

  if (view === "detail") {
    return <PerformanceClient onBack={() => setView("overview")} />;
  }
  return <PerformanceOverviewClient onOpen={() => setView("detail")} />;
}
