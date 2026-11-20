// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import MonthCalendar from "./MonthCalendar";
import type { DayRecord } from "./monthView";

const day = (n: number, status: string, extra: Partial<DayRecord> = {}): DayRecord => ({
  date: `2026-11-${String(n).padStart(2, "0")}`, day_short: "", day_num: n, status, status_label: status,
  clock_in: null, clock_out: null, total_hours: 0, is_flagged: false, record_id: null, ...extra,
});

afterEach(() => cleanup());

function show(days: DayRecord[]) {
  render(<MonthCalendar days={days} month="2026-11" todayISO="2026-11-20" highlight="" selectedDate={null} onSelect={vi.fn()} />);
}

describe("work from home on the month calendar", () => {
  it("marks a work-from-home day with a WFH tag beside its status", () => {
    show([day(19, "half_day", { clock_in: "16:39", clock_out: "18:16", total_hours: 1.6, is_wfh: true, record_id: "r19" })]);
    const cell = screen.getByRole("button", { name: /^19 November: .*Work from home/ });
    expect(cell.textContent).toContain("WFH");
    expect(cell.textContent).toContain("Half Day");            // the status is still there
  });

  it("marks an approved work-from-home day that has no punch (Absent or Not marked)", () => {
    show([day(10, "absent", { is_wfh: true })]);
    expect(screen.getByRole("button", { name: /^10 November: .*Work from home/ }).textContent).toContain("WFH");
  });

  it("shows no tag on an ordinary day", () => {
    show([day(18, "absent")]);
    expect(screen.getByRole("button", { name: /^18 November:/ }).textContent).not.toContain("WFH");
  });
});
