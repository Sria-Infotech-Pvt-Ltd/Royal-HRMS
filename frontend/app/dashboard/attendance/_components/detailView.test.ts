import { describe, expect, it } from "vitest";
import { PALETTE } from "./attendancePalette";
import { CORRECTION_STATUS, auditEventColour, dateCaption, detailBanners, formatEventLabel, longDate } from "./detailView";

const day = (overrides: Record<string, unknown> = {}) => ({ status_key: "present", clock_in: "09:05", clock_out: "18:10", punches: [{}, {}], is_late: false, is_early_exit: false, ...overrides });

describe("detailBanners", () => {
  it("has nothing to say about an ordinary full day", () => {
    expect(detailBanners(day())).toEqual([]);
  });

  it("says plainly that no punch was recorded, in red for an absent day and in the calm Not-marked colour otherwise", () => {
    const absent = detailBanners(day({ status_key: "absent", clock_in: "—", clock_out: "—", punches: [] }));
    expect(absent).toHaveLength(1);
    expect([absent[0].title, absent[0].colour]).toEqual(["No punch recorded", PALETTE.absent]);
    expect(absent[0].hint).toContain("use Edit");
    const unmarked = detailBanners(day({ status_key: "no_record", clock_in: "—", clock_out: "—", punches: [] }));
    expect(unmarked[0].colour).toBe(PALETTE.not_marked);
  });

  it("explains a day when no attendance is expected: leave, week off, holiday", () => {
    expect(detailBanners(day({ status_key: "on_leave", clock_in: "—", punches: [] }))[0]).toMatchObject({ title: "On approved leave", colour: PALETTE.on_leave });
    expect(detailBanners(day({ status_key: "weekly_off", punches: [] }))[0].title).toBe("Week off");
    expect(detailBanners(day({ status_key: "holiday", punches: [] }))[0].title).toBe("Public holiday");
    expect(detailBanners(day({ status_key: "weekly_off", punches: [] }))).toHaveLength(1);   // never also "no punch"
  });

  it("flags a missing clock-out, a late arrival and an early exit, each with its own colour", () => {
    expect(detailBanners(day({ status_key: "incomplete", clock_out: "—", punches: [{}] }))[0]).toMatchObject({ title: "Clocked in but never clocked out", colour: PALETTE.incomplete });
    const both = detailBanners(day({ is_late: true, is_early_exit: true }));
    expect(both.map(banner => banner.title)).toEqual(["Arrived late", "Left early"]);
    expect(both.every(banner => banner.colour === PALETTE.late)).toBe(true);
  });

  it("does not call a day 'no punch' when punches exist even if the times are blank", () => {
    expect(detailBanners(day({ clock_in: "—", clock_out: "—", punches: [{}] }))).toEqual([]);
  });
});

describe("labels", () => {
  it("writes event names and dates for people", () => {
    expect(formatEventLabel("CORRECTION_REQUESTED")).toBe("Correction Requested");
    expect(longDate("2026-11-17")).toBe("Tuesday, 17 November 2026");
    expect(dateCaption("2026-11-17", "2026-11-18")).toBe("Tuesday · Yesterday");
  });
  it("colours every correction status and the audit events", () => {
    expect(Object.values(CORRECTION_STATUS).map(status => status.label)).toEqual(["Pending", "Waiting for HR", "Approved", "Rejected"]);
    expect(auditEventColour("CLOCK_IN")).toBe(PALETTE.present);
    expect(auditEventColour("SOMETHING_NEW")).toBe(PALETTE.weekly_off);
  });
});
