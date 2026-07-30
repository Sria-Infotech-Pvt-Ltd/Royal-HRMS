import { getSession } from "@/lib/session";
import HRDashboard       from "./_components/HRDashboard";
import AdminDashboard    from "./_components/AdminDashboard";
import ManagerDashboard  from "./_components/ManagerDashboard";
import EmployeeDashboard from "./_components/EmployeeDashboard";

function resolveDashboard(session: {
  is_superuser?:   boolean;
  can_manage_team?: boolean;
  permissions?:    string[];
}) {
  if (session?.is_superuser)     return "admin";
  if (session?.can_manage_team)  return "manager";
  const perms = new Set(session?.permissions ?? []);
  if (perms.has("employees.view")) return "hr";
  return "employee";
}

export default async function DashboardPage() {
  const session = await getSession();
  const key     = resolveDashboard(session ?? {});
  const sess    = session!;

  if (key === "admin")   return <AdminDashboard   session={sess} />;
  if (key === "hr")      return <HRDashboard      session={sess} />;
  if (key === "manager") return <ManagerDashboard session={sess} />;
  return <EmployeeDashboard session={sess} />;
}
