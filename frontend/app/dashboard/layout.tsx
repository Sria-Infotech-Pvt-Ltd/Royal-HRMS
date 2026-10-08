import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import DashboardShell from "@/components/dashboard/DashboardShell";
import FaceModelPreloader from "@/components/FaceModelPreloader";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session) redirect("/login");

  return (
    <DashboardShell session={session}>
      <FaceModelPreloader />
      {children}
    </DashboardShell>
  );
}
