import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import OrgChartClient from "./_components/OrgChartClient";

export default async function OrgChartPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  return <OrgChartClient />;
}
