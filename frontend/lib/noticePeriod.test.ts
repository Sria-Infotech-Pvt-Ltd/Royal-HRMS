import { describe, expect, it } from "vitest";
import { expectedLastWorkingDay, formatNoticeDate, formatNoticePeriod, noticePeriodInputError, noticeRemainingLabel } from "./noticePeriod";

describe("noticeRemainingLabel", () => {
  it("shows 0 days remaining on the last working day", () => {
    expect(noticeRemainingLabel(0, "serving")).toBe("0 days remaining");
  });

  it("uses singular for one day", () => {
    expect(noticeRemainingLabel(1, "serving")).toBe("1 day remaining");
  });

  it("shows the count for a future last working day", () => {
    expect(noticeRemainingLabel(12, "serving")).toBe("12 days remaining");
  });

  it("marks the notice completed once the last working day has passed", () => {
    expect(noticeRemainingLabel(0, "completed")).toBe("Notice completed");
  });

  it("falls back to a dash when there is no countdown", () => {
    expect(noticeRemainingLabel(null, null)).toBe("—");
  });
});

describe("formatNoticeDate", () => {
  it("formats a plain date without shifting the day", () => {
    expect(formatNoticeDate("2026-10-31")).toBe("31 Oct 2026");
  });

  it("returns a dash for missing or invalid values", () => {
    expect(formatNoticeDate(null)).toBe("—");
    expect(formatNoticeDate("not-a-date")).toBe("—");
  });
});


describe("formatNoticePeriod", () => {
  it("shows days or Not assigned", () => {
    expect(formatNoticePeriod(30)).toBe("30 days");
    expect(formatNoticePeriod(1)).toBe("1 day");
    expect(formatNoticePeriod(0)).toBe("0 days");
    expect(formatNoticePeriod(null)).toBe("Not assigned");
    expect(formatNoticePeriod(undefined)).toBe("Not assigned");
  });
});

describe("noticePeriodInputError", () => {
  it("accepts blank and whole days up to 365", () => {
    expect(noticePeriodInputError("")).toBeNull();
    expect(noticePeriodInputError("90")).toBeNull();
    expect(noticePeriodInputError("365")).toBeNull();
  });
  it("rejects decimals, negatives, text and over 365", () => {
    expect(noticePeriodInputError("30.5")).toMatch(/whole/);
    expect(noticePeriodInputError("-1")).toMatch(/whole/);
    expect(noticePeriodInputError("abc")).toMatch(/whole/);
    expect(noticePeriodInputError("366")).toMatch(/365/);
  });
});

describe("expectedLastWorkingDay", () => {
  it("adds calendar days, across months and leap years", () => {
    expect(expectedLastWorkingDay("2026-10-01", 30)).toBe("2026-10-31");
    expect(expectedLastWorkingDay("2026-12-15", 30)).toBe("2027-01-14");
    expect(expectedLastWorkingDay("2028-02-01", 30)).toBe("2028-03-02");
    expect(expectedLastWorkingDay("2026-10-01", 0)).toBe("2026-10-01");
  });
  it("is null without a date or a notice period", () => {
    expect(expectedLastWorkingDay("", 30)).toBeNull();
    expect(expectedLastWorkingDay("2026-10-01", null)).toBeNull();
  });
});
