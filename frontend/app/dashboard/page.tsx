import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import HRDashboard       from "./_components/HRDashboard";
import ManagerDashboard  from "./_components/ManagerDashboard";

// A superuser/system_admin always holds employees.view (confirmed — see
// Role "system_admin"'s seeded permissions), so they see the same
// Workforce Dashboard an HR user does — this app has one consistent
// dashboard layout, not a separate admin-only variant (AdminDashboard.tsx
// is no longer routed to; kept only for reference/rollback, not deleted
// outright in case something still imports it directly).
function resolveDashboard(session: {
  is_superuser?:   boolean;
  can_manage_team?: boolean;
  permissions?:    string[];
}) {
  if (session?.can_manage_team)  return "manager";
  const perms = new Set(session?.permissions ?? []);
  if (session?.is_superuser || perms.has("employees.view")) return "hr";
  return "employee";
}

export default async function DashboardPage() {
  const session = await getSession();
  const key     = resolveDashboard(session ?? {});
  const sess    = session!;

  if (key === "hr")      return <HRDashboard      session={sess} />;
  if (key === "manager") return <ManagerDashboard session={sess} />;
  // An employee's real home is the ESS module (frontend/app/dashboard/ess) —
  // the old EmployeeDashboard.tsx Home-only widget is superseded by ESS's
  // own Home tab, which covers the same ground plus the other 13 tabs.
  redirect("/dashboard/ess");
}
