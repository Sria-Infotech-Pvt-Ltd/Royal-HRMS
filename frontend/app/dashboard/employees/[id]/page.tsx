import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { canViewEmployeeWorkspace } from "@/lib/dashboardHome";
import { viewWorkspacePath } from "@/lib/viewAs";

// There is no separate employee profile screen: opening an employee shows their workspace (what they see after
// login), read-only, for people allowed to (employees.view_workspace). Anyone else goes back to the directory.
export default async function EmployeePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await getSession();
  if (!session) redirect("/login");
  redirect(canViewEmployeeWorkspace(session as { is_superuser?: boolean; permissions?: string[] }) ? viewWorkspacePath(id) : "/dashboard/employees");
}
