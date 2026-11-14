"use client";

// Who did what to a timesheet and when, oldest first. Every submit, send-back, approval and unlock is listed with its reason.

import type { TimesheetEvent } from "@/types/timesheet";

const EVENT_LABEL: Record<TimesheetEvent["event_type"], string> = {
  submitted: "Submitted", resubmitted: "Resubmitted", returned: "Sent back", approved: "Approved", unlocked: "Reopened by HR",
};

interface Props {
  events: TimesheetEvent[];
}

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function TimesheetHistory({ events }: Props) {
  if (events.length === 0) return <p style={{ fontSize: 12.5, color: "var(--muted)", margin: 0 }}>Nothing has happened to this timesheet yet.</p>;
  return (
    <ol aria-label="Timesheet history" style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
      {events.map(event => (
        <li key={event.id} style={{ fontSize: 12.5, color: "var(--ink)" }}>
          <b>{EVENT_LABEL[event.event_type]}</b>
          {event.actor ? ` by ${event.actor.name}` : ""} <span style={{ color: "var(--muted)" }}>· {when(event.at)}</span>
          {event.reason && <div style={{ color: "var(--muted)", marginTop: 2 }}>“{event.reason}”</div>}
        </li>
      ))}
    </ol>
  );
}
