import { describe, expect, it } from "vitest";
import type { KindCount } from "@/lib/approvalOverview";
import { countOrDash, greetingFor, initialsOf, pendingApprovalsForMe, pendingRequestRows, relativeTime, totalPending } from "./hrHome";

const TEAM: KindCount[] = [
  { kind: "leave", pending: 4, needsMyAction: 3 },
  { kind: "wfh", pending: 2, needsMyAction: 2 },
  { kind: "expense", pending: 2, needsMyAction: 0 },
  { kind: "attendance_correction", pending: 1, needsMyAction: 1 },
  { kind: "separation", pending: 3, needsMyAction: 0 },
];

describe("pendingRequestRows", () => {
  it("builds the five rows of the design from the real counts, in order", () => {
    const rows = pendingRequestRows({ team: TEAM, face: 3 });
    expect(rows.map(row => [row.label, row.count])).toEqual([
      ["Face Registration", 3], ["Leave Requests", 4], ["Work From Home", 2], ["Expense Requests", 2], ["Other Requests", 4],
    ]);
    expect(totalPending(rows)).toBe(15);
  });

  it("leaves out each workflow the viewer cannot approve, not just all of them", () => {
    const onlyLeave: KindCount[] = [{ kind: "leave", pending: 2, needsMyAction: 2 }];
    expect(pendingRequestRows({ team: onlyLeave, face: null }).map(row => row.key)).toEqual(["leave"]);
  });

  it("leaves out a workflow the viewer cannot approve instead of showing zero", () => {
    expect(pendingRequestRows({ team: null, face: 1 }).map(row => row.key)).toEqual(["face"]);
    expect(pendingRequestRows({ team: TEAM, face: null }).map(row => row.key)).not.toContain("face");
    expect(pendingRequestRows({ team: null, face: null })).toEqual([]);
  });

  it("shows zeros, not invented numbers, when nothing is waiting", () => {
    const rows = pendingRequestRows({ team: [], face: 0 });
    expect(rows.every(row => row.count === 0)).toBe(true);
  });
});

describe("pendingApprovalsForMe", () => {
  it("counts only what needs this person's own decision, plus their Face ID queue", () => {
    expect(pendingApprovalsForMe({ team: TEAM, face: 3 })).toBe(3 + 2 + 0 + 1 + 0 + 3);
    expect(pendingApprovalsForMe({ team: null, face: null })).toBe(0);
  });
});

describe("display helpers", () => {
  it("greets by the hour", () => {
    expect([greetingFor(9), greetingFor(14), greetingFor(20)]).toEqual(["Good morning", "Good afternoon", "Good evening"]);
  });

  it("makes initials", () => {
    expect(initialsOf("Samreen UAT")).toBe("SU");
    expect(initialsOf("")).toBe("?");
  });

  it("says how long ago something happened", () => {
    const now = new Date("2026-11-05T12:00:00Z");
    expect(relativeTime("2026-11-05T11:50:00Z", now)).toBe("10 minutes ago");
    expect(relativeTime("2026-11-05T11:00:00Z", now)).toBe("1 hour ago");
    expect(relativeTime("2026-11-03T12:00:00Z", now)).toBe("2 days ago");
    expect(relativeTime("2026-11-05T12:00:00Z", now)).toBe("just now");
  });

  it("shows a dash, never a made-up number, when there is no value", () => {
    expect(countOrDash(null)).toBe("—");
    expect(countOrDash(undefined)).toBe("—");
    expect(countOrDash(0)).toBe("0");
    expect(countOrDash(12)).toBe("12");
  });
});
