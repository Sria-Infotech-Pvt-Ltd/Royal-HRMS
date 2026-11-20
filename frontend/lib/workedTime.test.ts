import { describe, expect, it } from "vitest";
import { formatBreak, totalAfterPunchOut } from "./workedTime";

describe("totalAfterPunchOut", () => {
  it("uses the record's own figure when the server sent it", () => {
    expect(totalAfterPunchOut({ total_seconds: 9 * 3600 + 31, worked_minutes: 8 * 60 })).toBe(8 * 3600);
  });
  it("falls back to the gross total for an older server answer", () => {
    expect(totalAfterPunchOut({ total_seconds: 5000 })).toBe(5000);
    expect(totalAfterPunchOut(null)).toBe(0);
  });
});

describe("formatBreak", () => {
  it("says the break in hours or minutes, and nothing for none", () => {
    expect(formatBreak(3600)).toBe("1h");
    expect(formatBreak(1800)).toBe("30 min");
    expect(formatBreak(5400)).toBe("1h 30m");
    expect(formatBreak(0)).toBe("");
    expect(formatBreak(undefined)).toBe("");
  });
});
