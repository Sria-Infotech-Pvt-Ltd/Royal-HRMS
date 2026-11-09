import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { resolveDashboard } from "@/lib/dashboardHome";
import HRDashboard from "./_components/HRDashboard";

// Superusers see the Workforce Dashboard. Everyone else — employees, team managers and HR alike — lands on the
// employee-style workspace (frontend/app/dashboard/ess); extra permissions add modules to the top bar, they do not
// change the home screen. A team manager's tools are on /dashboard/team (Team in the top bar).
export default async function DashboardPage() {
  const session = await getSession();
  if (session && resolveDashboard(session) === "hr") return <HRDashboard session={session} />;
  redirect("/dashboard/ess");
}
