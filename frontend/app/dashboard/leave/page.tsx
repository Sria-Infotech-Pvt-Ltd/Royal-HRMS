import LeavePageClient from "./_client";

interface Props {
  searchParams: Promise<{ tab?: string }>;
}

export default async function LeavePage({ searchParams }: Props) {
  const { tab } = await searchParams;
  return <LeavePageClient initialTab={tab === "apply" ? "apply" : "dashboard"} />;
}
