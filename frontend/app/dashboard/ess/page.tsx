import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import { isViewAsTarget } from "@/lib/viewAs";
import EssShellClient from "./_client";

// My Workspace — a single consolidated entry point that tabs together the
// self-service pages that already exist as separate top-level routes
// (Profile, My Attendance, Leave, My Payslips, Document Center, Separation,
// My Requests). Each tab renders that existing page's own real client
// component directly — no new data-fetching logic, no duplicated pages. The
// old routes keep working unchanged for anyone with them bookmarked; this is
// an additional entry point, not a replacement.
//
// With ?as=<employee id or code>, someone allowed to (employees.view_workspace, enforced by the server) sees that
// employee's own workspace, read-only.
export default async function EssPage({ searchParams }: { searchParams: Promise<{ as?: string }> }) {
  const session = await getSession();
  if (!session) redirect("/login");
  const { as: viewAs } = await searchParams;
  return <EssShellClient session={session} viewAsEmployee={isViewAsTarget(viewAs) ? viewAs : undefined} />;
}
