import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import EssShellClient from "./_client";

// My Workspace — a single consolidated entry point that tabs together the
// self-service pages that already exist as separate top-level routes
// (Profile, My Attendance, Leave, My Payslips, Document Center, Separation,
// My Requests). Each tab renders that existing page's own real client
// component directly — no new data-fetching logic, no duplicated pages. The
// old routes keep working unchanged for anyone with them bookmarked; this is
// an additional entry point, not a replacement.
export default async function EssPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  return <EssShellClient session={session} />;
}
