import { describe, expect, it } from "vitest";
import type { AttendanceStatus } from "@/types/employeeDashboard";
import { formatWorked, isDayComplete } from "./dayComplete";

const status = (change: Partial<AttendanceStatus>): AttendanceStatus => ({
  clocked_in: false, clock_in_time: "09:02", clock_out_time: "18:10", working_hours: "08:52", can_clock_in: true, can_clock_out: false, ...change,
});

describe("isDayComplete", () => {
  it("is true only after a punch-in and a punch-out, while punched out", () => {
    expect(isDayComplete(status({}))).toBe(true);
    expect(isDayComplete(status({ clocked_in: true }))).toBe(false);          // back in after a break
    expect(isDayComplete(status({ clock_in_time: null }))).toBe(false);       // never punched in
    expect(isDayComplete(status({ clock_out_time: null }))).toBe(false);      // no punch-out yet
    expect(isDayComplete(null)).toBe(false);
  });
});

describe("formatWorked", () => {
  it("turns HH:MM into hours and minutes", () => {
    expect(formatWorked("08:52")).toBe("8h 52m");
    expect(formatWorked("00:05")).toBe("0h 05m");
    expect(formatWorked("")).toBe("—");
    expect(formatWorked(null)).toBe("—");
  });
});
