import { describe, expect, it } from "vitest";
import { formatSeconds, todayView } from "./attendanceToday";
import type { AttendancePunch, AttendanceToday } from "@/types/dashboard";

const punch = (type: "IN" | "OUT", time: string): AttendancePunch => ({
  type, time, location: "Office", attendance_mode: "office", is_inside_geofence: true, calculated_distance: 0,
});
const day = (over: Partial<AttendanceToday> = {}): AttendanceToday => ({
  is_clocked_in: false, punches: [], total_seconds: 0, session_seconds: 0, date_display: "27 Oct", ...over,
});

describe("todayView", () => {
  it("shows loading only before the first response", () => {
    expect(todayView(null, true, null)).toEqual({ kind: "loading" });
    // a refresh after a punch keeps the previous data on screen
    expect(todayView(day({ punches: [punch("IN", "09:30")], is_clocked_in: true }), true, null).kind).toBe("present");
  });

  it("shows an error (not 'not clocked in') when the request fails", () => {
    expect(todayView(null, false, "Request failed.")).toEqual({ kind: "error", message: "Couldn't load today's attendance." });
  });

  it("shows not clocked in when there are no punches", () => {
    expect(todayView(day(), false, null)).toEqual({ kind: "empty" });
  });

  it("after clock in: clocked in, first punch shown, no punch out yet", () => {
    expect(todayView(day({ is_clocked_in: true, punches: [punch("IN", "09:30")] }), false, null)).toMatchObject({
      kind: "present", isClockedIn: true, firstIn: "09:30", lastOut: "—", total: "—",
    });
  });

  it("after clock out: clocked out with first in, last out and total time", () => {
    const v = todayView(day({ punches: [punch("IN", "09:30"), punch("OUT", "18:05")], total_seconds: 30900 }), false, null);
    expect(v).toMatchObject({ kind: "present", isClockedIn: false, firstIn: "09:30", lastOut: "18:05", total: "8h 35m" });
  });

  it("formats seconds as hours and minutes", () => {
    expect(formatSeconds(0)).toBe("0h 0m");
    expect(formatSeconds(3660)).toBe("1h 1m");
  });
});
