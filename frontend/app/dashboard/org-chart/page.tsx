import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import OrgStructureClient from "./_components/OrgStructureClient";

export default async function OrgChartPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  return <OrgStructureClient />;
}
