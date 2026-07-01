import { getSession } from "@/lib/session";
import LeavePageClient from "./_client";

export default async function LeavePage() {
  const session = await getSession();
  return <LeavePageClient role={session?.role ?? "employee"} />;
}
