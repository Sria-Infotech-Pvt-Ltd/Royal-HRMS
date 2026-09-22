import MyAttendanceClient from "./_client";

interface Props {
  searchParams: Promise<{ new?: string }>;
}

export default async function MyAttendancePage({ searchParams }: Props) {
  const { new: autoOpenNew } = await searchParams;
  return <MyAttendanceClient autoOpenNew={autoOpenNew === "1"} />;
}
