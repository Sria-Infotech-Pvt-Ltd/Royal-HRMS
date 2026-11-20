// How today's worked time is shown, so the live timer and the figure after punch-out line up.
//
// The live timer counts real time (gross). The saved attendance record takes the company's break off and works in whole
// minutes. The server sends both: `total_seconds` (gross) and `worked_minutes` (the record's own figure, after the break).
// While punched in the screen shows the ticking gross time and says the break comes off at punch-out; once punched out it shows
// the record's figure, so it is exactly the number HR and the attendance calendar show.
import type { TodaySession } from "@/types/attendance";

/** Seconds to show as "total today" once the person is out: the record's own figure when the server sent it, else the gross total. */
export function totalAfterPunchOut(session: Pick<TodaySession, "total_seconds" | "worked_minutes"> | null | undefined): number {
  if (!session) return 0;
  return session.worked_minutes === undefined ? session.total_seconds : session.worked_minutes * 60;
}

/** "1h" for a whole number of hours, "45 min" otherwise; "" when there is no break. */
export function formatBreak(breakSeconds: number | undefined): string {
  const minutes = Math.round((breakSeconds ?? 0) / 60);
  if (minutes <= 0) return "";
  return minutes % 60 === 0 ? `${minutes / 60}h` : minutes > 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes} min`;
}
