"use client";

// Right-hand summary of the leave request form: the selected type's balance and what this
// request will use. Shows the quick client estimate until the server preview (which knows
// holidays and week-offs) arrives, so the two never disagree on screen.

import { fmtDate, type LeaveBalance, type LeavePreview, type LeaveTypeConfig } from "../_data";
import type { LeaveForm } from "./applyLeaveFormHelpers";

interface Props {
  leaveType: LeaveTypeConfig;
  balance: LeaveBalance | undefined;
  available: number;
  form: LeaveForm;
  isHalfDay: boolean;
  workDays: number;
  isOverLimit: boolean;
  preview: LeavePreview | null;
  isPreviewLoading: boolean;
  isInsufficientBalance: boolean;
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "warn" }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-[13px]">
      <span className="text-[var(--on-variant)]">{label}</span>
      <span className={`font-semibold ${tone === "warn" ? "text-[var(--warn)]" : "text-[var(--on-bg)]"}`}>{value}</span>
    </div>
  );
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

export default function LeaveRequestSummary({
  leaveType, balance, available, form, isHalfDay, workDays, isOverLimit, preview, isPreviewLoading, isInsufficientBalance,
}: Props) {
  const total = balance ? Number(balance.total_days) : 0;
  const used = balance ? Number(balance.used_days) : 0;
  const percentLeft = total > 0 ? Math.min(100, Math.round((available / total) * 100)) : 0;
  const endDate = isHalfDay ? form.from_date : form.to_date;
  const hasDates = !!form.from_date && !!endDate;
  const leaveDays = preview ? preview.actual_leave_days : workDays;
  const lopDays = preview?.lop_days ?? 0;
  const holidays = preview?.company_holidays ?? [];
  const weekOffs = preview?.week_offs ?? [];

  return (
    <aside className="flex flex-col gap-5 self-start rounded-xl border border-[var(--outline-v)] bg-[var(--bg-low)] p-4">
      <section>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--on-variant)]">Leave balance</p>
        <p className="text-sm font-semibold text-[var(--on-bg)]">{leaveType.label}</p>
        {leaveType.isLwp ? (
          <p className="mt-1 text-[13px] text-[var(--on-variant)]">Unpaid leave — no balance limit.</p>
        ) : (
          <>
            <p className="mt-1 text-[13px] text-[var(--on-variant)]">
              <span className="text-2xl font-semibold text-[var(--on-bg)]">{available}</span> of {total} days remaining
            </p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--bg-high)]">
              <div className="h-full rounded-full bg-[var(--primary)]" style={{ width: `${percentLeft}%` }} />
            </div>
            <p className="mt-1.5 text-xs text-[var(--on-variant)]">{used} used this year</p>
          </>
        )}
      </section>

      <section className="border-t border-[var(--outline-v)] pt-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--on-variant)]">This request</p>
        {!hasDates ? (
          <p className="text-[13px] text-[var(--on-variant)]">Choose your dates to see how many leave days this will use.</p>
        ) : (
          <div className="flex flex-col gap-2">
            <Row label="Period" value={isHalfDay || form.from_date === endDate ? fmtDate(form.from_date) : `${fmtDate(form.from_date)} – ${fmtDate(endDate)}`} />
            <Row label="Leave days" value={String(leaveDays)} tone={isOverLimit ? "warn" : undefined} />
            {preview && <Row label="Calendar days" value={String(preview.calendar_days)} />}
            {!leaveType.isLwp && <Row label="Balance after" value={String(Math.max(0, preview ? preview.available_balance - preview.leave_days_used : available - workDays))} />}
            {lopDays > 0 && <Row label="Loss of pay" value={plural(lopDays, "day")} tone="warn" />}
            {isPreviewLoading && !preview && (
              <p className="flex items-center gap-1.5 text-xs text-[var(--on-variant)]"><i className="ti ti-loader-2 animate-spin" /> Checking holidays and balance…</p>
            )}
            {(holidays.length > 0 || weekOffs.length > 0) && (
              <div className="mt-1 border-t border-[var(--outline-v)] pt-2.5 text-xs text-[var(--on-variant)]">
                <p className="mb-1 font-semibold">Not counted</p>
                <ul className="flex flex-col gap-0.5">
                  {holidays.map(holiday => <li key={`${holiday.date}-${holiday.name}`}>{holiday.name} · {holiday.date}</li>)}
                  {weekOffs.map(weekOff => <li key={weekOff.date}>Week-off · {fmtDate(weekOff.date)} ({weekOff.day})</li>)}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>

      {isOverLimit && !preview && (
        <p className="rounded-lg border border-[var(--error)] bg-[var(--error-c)] px-3 py-2 text-xs text-[var(--error)]">
          This is more than your remaining balance by {workDays - available} day{workDays - available === 1 ? "" : "s"}.
        </p>
      )}
      {preview?.warning && (
        <p className="rounded-lg border border-[var(--info)] bg-[var(--info-c)] px-3 py-2 text-xs text-[var(--info)]">{preview.warning}</p>
      )}
      {isInsufficientBalance && (
        <p className="rounded-lg border border-[var(--error)] bg-[var(--error-c)] px-3 py-2 text-xs text-[var(--error)]">
          Insufficient leave balance for these dates. This request cannot be submitted.
        </p>
      )}
    </aside>
  );
}
