import { describe, expect, it } from "vitest";
import { PALETTE } from "./attendancePalette";
import { OT_TYPES, durationLabel, minutesBetween, otStatusColour, otTypeColour, validateOtForm } from "./otEntry";

describe("minutesBetween and durationLabel", () => {
  it("measures a normal range and words it for people", () => {
    expect(minutesBetween("18:00", "20:00")).toBe(120);
    expect(minutesBetween("18:00", "18:45")).toBe(45);
    expect(durationLabel(120)).toBe("2h 00m");
    expect(durationLabel(90)).toBe("1h 30m");
    expect(durationLabel(45)).toBe("45m");
    expect(durationLabel(61)).toBe("1h 01m");
  });
  it("has no duration when a time is missing or the end is not after the start", () => {
    expect(minutesBetween("20:00", "18:00")).toBeNull();
    expect(minutesBetween("18:00", "18:00")).toBeNull();
    expect(minutesBetween("", "20:00")).toBeNull();
    expect(minutesBetween("18:00", "soon")).toBeNull();
  });
});

describe("validateOtForm", () => {
  const ok = { employee_id: "E1", date: "2026-11-18", ot_start: "18:00", ot_end: "20:00" };
  it("accepts a complete form", () => {
    expect(validateOtForm(ok)).toBeNull();
  });
  it("names the first problem, in the form's long-standing words", () => {
    expect(validateOtForm({ ...ok, employee_id: "" })).toBe("Please select an employee.");
    expect(validateOtForm({ ...ok, date: "" })).toBe("Please select a date.");
    expect(validateOtForm({ ...ok, ot_end: "17:00" })).toBe("OT end time must be after OT start time.");
    expect(validateOtForm({ ...ok, employee_id: "", date: "" })).toBe("Please select an employee.");
  });
});

describe("types and colours", () => {
  it("offers the three overtime types with the rates the old drop-down showed", () => {
    expect(OT_TYPES.map(type => [type.value, type.multiplier])).toEqual([["regular", "1.5×"], ["holiday", "2.0×"], ["weekly_off", "1.5×"]]);
  });
  it("colours statuses: approved green, rejected red, pending orange, anything else slate", () => {
    expect([otStatusColour("Approved"), otStatusColour("REJECTED"), otStatusColour("Pending"), otStatusColour("Paid")]).toEqual([PALETTE.present, PALETTE.absent, PALETTE.late, PALETTE.not_marked]);
  });
  it("colours a type from the text the server sends", () => {
    expect([otTypeColour("Holiday"), otTypeColour("Weekly Off"), otTypeColour("Regular")]).toEqual([PALETTE.holiday, PALETTE.on_leave, PALETTE.half_day]);
  });
});
