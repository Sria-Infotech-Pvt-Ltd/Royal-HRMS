import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { canOpenTeamDashboard } from "@/lib/dashboardHome";
import ManagerHomeDashboard from "../_components/ManagerHomeDashboard";

// The Manager dashboard. Managers land on their workspace at login and open this from the top bar or the profile menu.
export default async function TeamDashboardPage() {
  const session = await getSession();
  if (!session || !canOpenTeamDashboard(session as { can_manage_team?: boolean })) redirect("/dashboard");
  return <ManagerHomeDashboard session={session} />;
}
