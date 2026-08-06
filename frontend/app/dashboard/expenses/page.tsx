import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import ExpenseClaims from "./_components/ExpenseClaims";

interface Props {
  searchParams: Promise<{ new?: string }>;
}

export default async function ExpensesPage({ searchParams }: Props) {
  const session = await getSession();
  if (!session) redirect("/login");
  const { new: autoOpenNew } = await searchParams;
  return <ExpenseClaims autoOpenNew={autoOpenNew === "1"} />;
}
