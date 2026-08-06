import MyAttendanceClient from "./_client";

interface Props {
  searchParams: Promise<{ tab?: string; new?: string }>;
}

export default async function MyAttendancePage({ searchParams }: Props) {
  const { tab, new: autoOpenNew } = await searchParams;
  return (
    <MyAttendanceClient
      initialTab={tab === "corrections" ? "corrections" : "attendance"}
      autoOpenNew={autoOpenNew === "1"}
    />
  );
}
