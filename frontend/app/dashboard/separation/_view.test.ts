import { describe, expect, it } from "vitest";
import type { SeparationRequest } from "@/types/separation";
import { countSeparations, lastDayCountdown, statusGroup } from "./_view";

const row = (status: string, canApprove = false) => ({ status, can_approve: canApprove }) as unknown as SeparationRequest;

describe("statusGroup", () => {
  it("groups opaque status codes by keyword", () => {
    expect(statusGroup("pending")).toBe("waiting");
    expect(statusGroup("stage2_pending")).toBe("waiting");
    expect(statusGroup("approved")).toBe("approved");
    expect(statusGroup("completed")).toBe("approved");
    expect(statusGroup("rejected")).toBe("closed");
    expect(statusGroup("cancelled")).toBe("closed");
  });
});

describe("countSeparations", () => {
  it("counts each group and the requests waiting on this person", () => {
    const counts = countSeparations([row("pending", true), row("stage2_pending"), row("approved"), row("rejected"), row("cancelled")]);
    expect(counts).toEqual({ all: 5, waiting: 2, approved: 1, closed: 2, needsMe: 1 });
  });
});

describe("lastDayCountdown", () => {
  const today = "2026-11-18";
  it("says today, in N days, or N days ago", () => {
    expect(lastDayCountdown("2026-11-18", today)).toEqual({ label: "Today", tone: "soon" });
    expect(lastDayCountdown("2026-11-19", today)).toEqual({ label: "in 1 day", tone: "soon" });
    expect(lastDayCountdown("2026-12-31", today)).toEqual({ label: "in 43 days", tone: "later" });
    expect(lastDayCountdown("2026-11-13", today)).toEqual({ label: "5 days ago", tone: "passed" });
  });
  it("gives nothing without a date", () => {
    expect(lastDayCountdown(null, today)).toBeNull();
  });
});
