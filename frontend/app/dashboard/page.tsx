import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { resolveDashboard } from "@/lib/dashboardHome";
import HRDashboard from "./_components/HRDashboard";

// HR and superusers see the Workforce Dashboard. Everyone else — employees and team managers alike — lands on
// their workspace (frontend/app/dashboard/ess). A team manager's tools are on /dashboard/team, reached from
// the profile menu.
export default async function DashboardPage() {
  const session = await getSession();
  if (session && resolveDashboard(session) === "hr") return <HRDashboard session={session} />;
  redirect("/dashboard/ess");
}
