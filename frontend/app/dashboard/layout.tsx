import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import DashboardShell from "@/components/dashboard/DashboardShell";
import SessionKeepAlive from "@/components/dashboard/SessionKeepAlive";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session) redirect("/login");

  return (
    <>
      <SessionKeepAlive />
      <DashboardShell session={session}>{children}</DashboardShell>
    </>
  );
}
