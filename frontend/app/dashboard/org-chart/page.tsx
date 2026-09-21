import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import OrgChartPageClient from "./_components/OrgChartPageClient";

export default async function OrgChartPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  return <OrgChartPageClient />;
}
