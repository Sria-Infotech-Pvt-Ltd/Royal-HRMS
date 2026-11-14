"use client";

// The button on the Home and Attendance timesheet cards: opens this week's timesheet. Its label follows the sheet's state
// (Fill / Continue / Fix and resubmit / View). Inside My Workspace the parent passes `onOpen`, so it opens in place; elsewhere it
// is a link into the workspace. Hidden while an admin looks at someone else's workspace, because the timesheet always opens
// the signed-in person's own sheet.

import Link from "next/link";
import { getViewAsEmployee } from "@/lib/viewAs";
import { cardActionLabel } from "@/lib/timesheet";
import type { WeeklyTimesheetSummary } from "@/types/timesheet";

interface Props {
  summary: WeeklyTimesheetSummary;
  className: string;
  /** Open the timesheet for this week in place (inside the workspace). Without it, a link into the workspace is shown. */
  onOpen?: (weekStart: string) => void;
}

export default function TimesheetCardAction({ summary, className, onOpen }: Props) {
  if (getViewAsEmployee()) return null;
  const label = cardActionLabel(summary.timesheet_status);
  if (onOpen) return <button type="button" className={className} onClick={() => onOpen(summary.week_start)}>{label}</button>;
  return <Link className={className} href={`/dashboard/ess?tab=timesheet&week=${summary.week_start}`}>{label}</Link>;
}
