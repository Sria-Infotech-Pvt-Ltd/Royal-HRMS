import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";

// The timesheet now lives inside My Workspace (Attendance). This address stays valid for old links and bookmarks.
export default async function TimesheetPage({ searchParams }: { searchParams: Promise<{ [key: string]: string | string[] | undefined }> }) {
  const session = await getSession();
  if (!session) redirect("/login");
  const { week } = await searchParams;
  const requested = typeof week === "string" && /^\d{4}-\d{2}-\d{2}$/.test(week) ? `&week=${week}` : "";
  redirect(`/dashboard/ess?tab=timesheet${requested}`);
}
