import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { canOpenTeamDashboard } from "@/lib/dashboardHome";
import ManagerDashboard from "../_components/ManagerDashboard";

// The team manager's dashboard. Managers land on their workspace at login and open this from the profile menu.
export default async function TeamDashboardPage() {
  const session = await getSession();
  if (!session || !canOpenTeamDashboard(session as { can_manage_team?: boolean })) redirect("/dashboard");
  return <ManagerDashboard session={session} />;
}
