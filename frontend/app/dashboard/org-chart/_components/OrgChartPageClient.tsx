"use client";

import { useState } from "react";
import OrgOverviewClient from "./OrgOverviewClient";
import OrgStructureClient from "./OrgStructureClient";

export default function OrgChartPageClient() {
  const [view, setView] = useState<"overview" | "chart">("overview");
  const [initialUnitId, setInitialUnitId] = useState<string | undefined>(undefined);

  if (view === "chart") {
    return <OrgStructureClient onBack={() => setView("overview")} initialSelectedUnitId={initialUnitId} />;
  }
  return (
    <OrgOverviewClient
      onOpenChart={unitId => { setInitialUnitId(unitId); setView("chart"); }}
    />
  );
}
