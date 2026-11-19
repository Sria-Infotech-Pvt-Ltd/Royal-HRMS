import { describe, expect, it } from "vitest";
import { buildApprovalsLink, parseApprovalsLink } from "./approvalLink";

describe("approval links", () => {
  it("builds a link that opens Team Approvals on one type, status and month", () => {
    expect(buildApprovalsLink({ type: "leave", status: "rejected", month: "2026-11" }))
      .toBe("/dashboard/approvals?section=approvals&type=leave&status=rejected&month=2026-11");
  });

  it("leaves the month out when it is unknown or malformed", () => {
    expect(buildApprovalsLink({ type: "leave", status: "approved" })).toBe("/dashboard/approvals?section=approvals&type=leave&status=approved");
    expect(buildApprovalsLink({ type: "leave", status: "approved", month: "Nov 2026" })).not.toContain("month=");
  });

  it("reads the type, status and the whole month back out", () => {
    const filters = parseApprovalsLink(new URLSearchParams("section=approvals&type=leave&status=rejected&month=2026-11"));
    expect(filters).toEqual({ type: "leave", status: "rejected", dateFrom: "2026-11-01", dateTo: "2026-11-30" });
  });

  it("knows how long February is", () => {
    expect(parseApprovalsLink(new URLSearchParams("month=2028-02")).dateTo).toBe("2028-02-29");
    expect(parseApprovalsLink(new URLSearchParams("month=2027-02")).dateTo).toBe("2027-02-28");
  });

  it("ignores anything it does not recognise", () => {
    expect(parseApprovalsLink(new URLSearchParams("type=salary&status=maybe&month=2026-13"))).toEqual({});
    expect(parseApprovalsLink(null)).toEqual({});
  });
});
