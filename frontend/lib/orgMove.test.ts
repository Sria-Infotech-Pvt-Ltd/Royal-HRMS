import { describe, expect, it } from "vitest";
import { suggestSeats, todayIsoDate } from "./orgMove";

describe("suggestSeats", () => {
  const seats = [{ id: "s1", title: "Developer" }, { id: "s2", title: "Analyst" }, { id: "s3", title: "Tester" }];

  it("gives each person a seat with their own title first", () => {
    const result = suggestSeats([{ employeeId: "E1", title: "analyst" }, { employeeId: "E2", title: "Developer" }], seats);
    expect(result).toEqual({ E1: "s2", E2: "s1" });
  });

  it("fills the rest from the leftover seats and never gives one seat twice", () => {
    const result = suggestSeats(
      [{ employeeId: "E1", title: "Designer" }, { employeeId: "E2", title: "Tester" }, { employeeId: "E3", title: "Designer" }],
      seats,
    );
    expect(result.E2).toBe("s3");
    expect(new Set(Object.values(result)).size).toBe(3);
  });

  it("leaves people unmatched when there are not enough vacant seats", () => {
    const result = suggestSeats([{ employeeId: "E1", title: "X" }, { employeeId: "E2", title: "Y" }], [{ id: "s1", title: "Z" }]);
    expect(result).toEqual({ E1: "s1", E2: "" });
  });
});

describe("todayIsoDate", () => {
  it("is a YYYY-MM-DD date", () => {
    expect(todayIsoDate(new Date(2026, 10, 26, 23, 30))).toBe("2026-11-26");
  });
});
