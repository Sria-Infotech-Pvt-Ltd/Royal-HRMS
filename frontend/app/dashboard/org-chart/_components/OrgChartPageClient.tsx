"use client";

// Lands directly on the real Organization chart — no marketing-style landing screen.
import { useRouter } from "next/navigation";
import OrgStructureClient from "./OrgStructureClient";

export default function OrgChartPageClient() {
  const router = useRouter();
  // Back goes to the page before this one; when this page was opened directly there is none, so go to the dashboard.
  const goBack = () => { if (window.history.length > 1) router.back(); else router.push("/dashboard"); };
  return <OrgStructureClient onBack={goBack} />;
}
