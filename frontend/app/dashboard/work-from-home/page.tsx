import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import WorkFromHomeClient from "./_client";

export default async function WorkFromHomePage() {
  const session = await getSession();
  if (!session) redirect("/login");
  return <WorkFromHomeClient />;
}
