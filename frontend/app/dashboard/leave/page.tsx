import { getSession } from "@/lib/session";
import LeavePageClient from "./_client";

interface Props {
  searchParams: Promise<{ tab?: string }>;
}

export default async function LeavePage({ searchParams }: Props) {
  const session = await getSession();
  const { tab } = await searchParams;
  return <LeavePageClient role={session?.role ?? "employee"} initialTab={tab === "apply" ? "apply" : "dashboard"} />;
}
