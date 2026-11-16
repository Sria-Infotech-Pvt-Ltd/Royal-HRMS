"use client";

import StatusPill from "@/components/employees/StatusPill";
import { STATUS_LABEL, STATUS_TONE } from "@/lib/timesheet";
import type { TimesheetStatus } from "@/types/timesheet";

interface Props {
  status: TimesheetStatus;
  isLate?: boolean;
}

export default function TimesheetStatusBadge({ status, isLate = false }: Props) {
  return (
    <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
      <StatusPill label={STATUS_LABEL[status]} tone={STATUS_TONE[status]} />
      {isLate && status !== "draft" && <StatusPill label="Late" tone="warn" />}
    </span>
  );
}
