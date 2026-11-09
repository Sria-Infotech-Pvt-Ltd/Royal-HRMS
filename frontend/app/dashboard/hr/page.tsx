import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { hasHrDashboardAccess } from "@/lib/dashboardHome";
import HrHomeDashboard from "../_components/HrHomeDashboard";

// The dedicated HR dashboard. HR users also have their employee-style workspace at /dashboard/ess; the two are separate
// screens and a person switches between them from the top bar. The data is fetched from APIs that authorize on their
// own (employees.view), so this guard only decides what is shown.
export default async function HrDashboardPage() {
  const session = await getSession();
  if (!session || !hasHrDashboardAccess(session)) redirect("/dashboard");
  return <HrHomeDashboard session={session} />;
}
