import MyRequestsClient from "./_client";
import type { MyRequestKind } from "./_data";

interface Props {
  searchParams: Promise<{ tab?: string }>;
}

export default async function MyRequestsPage({ searchParams }: Props) {
  const { tab } = await searchParams;
  const initialTab: "all" | MyRequestKind =
    tab === "leave" || tab === "expense" || tab === "attendance_correction" || tab === "wfh" ? tab : "all";
  return <MyRequestsClient initialTab={initialTab} />;
}
