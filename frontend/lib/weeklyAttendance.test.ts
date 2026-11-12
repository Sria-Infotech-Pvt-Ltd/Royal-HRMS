import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { AttendanceTrend } from "@/components/dashboard/WorkforceWidgets";
import { MONDAY_FIRST_LABELS, toCurrentWeek } from "./weeklyAttendance";

// The backend's last 7 days, oldest first, ending today. Counts 10..16 make
// each day identifiable.
const lastSevenDays = (labels: string[]) => labels.map((label, index) => ({ label, count: 10 + index }));

describe("toCurrentWeek", () => {
  it("always returns Monday to Sunday", () => {
    const week = toCurrentWeek(lastSevenDays(["T", "F", "S", "S", "M", "T", "W"]), new Date(2026, 10, 11));
    expect(week.map(day => day.label)).toEqual([...MONDAY_FIRST_LABELS]);
    expect(week.map(day => day.label)).toEqual(["M", "T", "W", "T", "F", "S", "S"]);
  });

  it("midweek: fills Monday..today from the series and leaves the rest of the week empty (Wednesday 11 Nov 2026)", () => {
    // Series: Thu 5, Fri 6, Sat 7, Sun 8, Mon 9, Tue 10, Wed 11 (today)
    const week = toCurrentWeek(lastSevenDays(["T", "F", "S", "S", "M", "T", "W"]), new Date(2026, 10, 11));
    expect(week.map(day => day.count)).toEqual([14, 15, 16, null, null, null, null]);
    expect(week.map(day => day.isToday)).toEqual([false, false, true, false, false, false, false]);
  });

  it("Monday: only Monday has data", () => {
    // Series: Tue 3 … Mon 9 (today)
    const week = toCurrentWeek(lastSevenDays(["T", "W", "T", "F", "S", "S", "M"]), new Date(2026, 10, 9));
    expect(week.map(day => day.count)).toEqual([16, null, null, null, null, null, null]);
    expect(week[0].isToday).toBe(true);
  });

  it("Sunday: the whole series is this week, in order", () => {
    // Series: Mon 9 … Sun 15 (today)
    const week = toCurrentWeek(lastSevenDays(["M", "T", "W", "T", "F", "S", "S"]), new Date(2026, 10, 15));
    expect(week.map(day => day.count)).toEqual([10, 11, 12, 13, 14, 15, 16]);
    expect(week[6].isToday).toBe(true);
  });
});

describe("AttendanceTrend", () => {
  afterEach(() => vi.useRealTimers());

  it("renders bars Monday to Sunday with today emphasised and later days empty", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 11, 10, 0, 0)); // Wednesday
    const html = renderToStaticMarkup(createElement(AttendanceTrend, {
      data: lastSevenDays(["T", "F", "S", "S", "M", "T", "W"]), total: 20, loading: false,
    }));
    const labels = [...html.matchAll(/class="wf-col-lbl[^"]*">(\w)</g)].map(match => match[1]);
    expect(labels).toEqual(["M", "T", "W", "T", "F", "S", "S"]);
    expect(html).toMatch(/class="wf-col today"[^>]*title="16 present · 80% of headcount"/);
    expect(html.match(/class="wf-col upcoming"/g)).toHaveLength(4);
    expect(html.match(/<i class=/g)).toHaveLength(3); // bars only for Mon, Tue, Wed
  });
});
