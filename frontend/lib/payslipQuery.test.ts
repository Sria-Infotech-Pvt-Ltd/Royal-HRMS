import { describe, expect, it } from "vitest";
import { canRaiseQuery, queriesFor, validateQueryText, type PayslipQueryRow } from "./payslipQuery";

const NOW = new Date("2026-10-27T10:00:00Z");
const q = (over: Partial<PayslipQueryRow>): PayslipQueryRow => ({
  id: "q", payslip: "p1", description: "d", status: "open", resolution_note: "", resolved_by_name: null,
  resolved_at: null, created_at: "2026-10-27T09:00:00Z", ...over,
});

describe("canRaiseQuery", () => {
  it("allows sent or acknowledged payslips inside the window", () => {
    expect(canRaiseQuery({ status: "sent", query_deadline: "2026-10-28T10:00:00Z" }, NOW).allowed).toBe(true);
    expect(canRaiseQuery({ status: "acknowledged", query_deadline: null }, NOW).allowed).toBe(true);
  });

  it("blocks after the deadline, while a query is open, and before dispatch / after payment", () => {
    expect(canRaiseQuery({ status: "sent", query_deadline: "2026-10-27T09:59:59Z" }, NOW))
      .toEqual({ allowed: false, reason: "The query window for this payslip has closed." });
    expect(canRaiseQuery({ status: "queried" }, NOW).reason).toMatch(/already open/);
    expect(canRaiseQuery({ status: "draft" }, NOW).allowed).toBe(false);
    expect(canRaiseQuery({ status: "paid" }, NOW).allowed).toBe(false);
    expect(canRaiseQuery({ status: "resolved" }, NOW).allowed).toBe(false);
  });
});

describe("validateQueryText", () => {
  it("requires non-blank text within the length limit", () => {
    expect(validateQueryText("   ")).toBe("Please describe your query.");
    expect(validateQueryText("x".repeat(2001))).toMatch(/under 2000/);
    expect(validateQueryText("  HRA missing  ")).toBeNull();
  });
});

describe("queriesFor", () => {
  it("returns only this payslip's queries, newest first", () => {
    const rows = [
      q({ id: "old", created_at: "2026-10-01T00:00:00Z", status: "resolved", resolution_note: "Fixed" }),
      q({ id: "other", payslip: "p2" }),
      q({ id: "new", created_at: "2026-10-20T00:00:00Z" }),
    ];
    expect(queriesFor(rows, "p1").map(r => r.id)).toEqual(["new", "old"]);
    expect(queriesFor(null, "p1")).toEqual([]);
  });
});
