"use client";

// The "Record leave" form of the Employee Directory's Leave dialog: HR records leave on someone's behalf. It is
// final at once (balance deducted, attendance marked) — the server validates everything and needs leave.record.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import { formatDateSlash } from "@/lib/formatDate";

export type LeaveDuration = "full_day" | "first_half" | "second_half";

export const DURATION_OPTIONS: { value: LeaveDuration; label: string }[] = [
  { value: "full_day", label: "Full day" },
  { value: "first_half", label: "First half" },
  { value: "second_half", label: "Second half" },
];

/** Working days in the range, Saturdays and Sundays excluded (a half day counts 0.5). The server has the final say. */
export function estimateWorkingDays(from: string, to: string, duration: LeaveDuration): number {
  if (!from || !to) return 0;
  if (from === to && duration !== "full_day") return 0.5;
  const cursor = new Date(`${from}T00:00:00`);
  const end = new Date(`${to}T00:00:00`);
  let days = 0;
  while (cursor <= end) {
    const weekday = cursor.getDay();
    if (weekday !== 0 && weekday !== 6) days += 1;
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

export function useRecordEmployeeLeave(employeeCode: string, firstType: string, onRecorded: () => void) {
  const { showToast } = useToast();
  const [leaveType, setLeaveType] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [duration, setDuration] = useState<LeaveDuration>("full_day");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const type = leaveType || firstType;
  const days = estimateWorkingDays(from, to, duration);

  async function record() {
    if (!from) { setError("Start date is required."); return; }
    if (!to) { setError("End date is required."); return; }
    if (to < from) { setError("End date is before the start date."); return; }
    if (from !== to && duration !== "full_day") { setError("Half day applies to a single date only."); return; }
    if (!days) { setError("That range contains only weekly offs."); return; }
    setSaving(true);
    setError("");
    try {
      await clientApi.post(API.leave.recordForEmployee, {
        employee_id: employeeCode, leave_type: type, start_date: from, end_date: to, duration, reason: reason.trim(),
      });
      showToast(`Leave recorded — ${days} day${days === 1 ? "" : "s"} from ${formatDateSlash(from)}.`, "success");
      setFrom(""); setTo(""); setReason(""); setDuration("full_day");
      onRecorded();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Could not record this leave.");
    } finally {
      setSaving(false);
    }
  }

  return { type, setLeaveType, from, setFrom, to, setTo, duration, setDuration, reason, setReason, days, error, saving, record };
}
