import { describe, expect, it } from "vitest";
import { formatNoticeDate, noticeRemainingLabel } from "./noticePeriod";

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
