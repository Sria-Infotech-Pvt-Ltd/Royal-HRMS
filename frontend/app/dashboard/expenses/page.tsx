import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import ExpenseClaims from "./_components/ExpenseClaims";

export default async function ExpensesPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  return <ExpenseClaims />;
}
