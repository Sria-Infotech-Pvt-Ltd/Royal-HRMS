import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import DashboardShell from "@/components/dashboard/DashboardShell";
import { PreviewRoleProvider } from "@/hooks/usePreviewRole";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session) redirect("/login");

  return (
    <PreviewRoleProvider>
      <DashboardShell session={session}>{children}</DashboardShell>
    </PreviewRoleProvider>
  );
}
