import { describe, expect, it } from "vitest";
import {
  cancellationBadge, cancellationReasonError, daysBetweenInclusive, delegationState, escalationTimeline,
  localToday, rejectRemarksError, toEscalationForm, validateDelegation, validateEscalation,
  type DelegationForm, type EscalationForm,
} from "./approvalWorkflows";

const esc = (over: Partial<EscalationForm> = {}): EscalationForm => ({
  is_enabled: true, reminder_after_days: 1, first_escalation_after_days: 2, second_escalation_after_days: 3,
  escalation_head: "", applies_to_leave: true, applies_to_attendance: true, ...over,
});

const del = (over: Partial<DelegationForm> = {}): DelegationForm => ({
  delegate: "u2", start_date: "2026-11-11", end_date: "2026-11-20", workflows: ["leave"], reason: "", ...over,
});

describe("validateEscalation", () => {
  it("accepts the recommended defaults", () => {
    expect(validateEscalation(esc())).toEqual({});
  });
  it("needs the reminder before the first escalation", () => {
    expect(validateEscalation(esc({ reminder_after_days: 2 })).reminder_after_days).toMatch(/before/);
    expect(validateEscalation(esc({ reminder_after_days: 0 }))).toEqual({});
  });
  it("rejects out-of-range and fractional values", () => {
    expect(validateEscalation(esc({ first_escalation_after_days: 0 })).first_escalation_after_days).toBeTruthy();
    expect(validateEscalation(esc({ second_escalation_after_days: 31 })).second_escalation_after_days).toBeTruthy();
    expect(validateEscalation(esc({ reminder_after_days: 1.5 })).reminder_after_days).toBeTruthy();
  });
  it("needs a request type only when enabled", () => {
    const none = { applies_to_leave: false, applies_to_attendance: false };
    expect(validateEscalation(esc(none)).applies_to_leave).toBeTruthy();
    expect(validateEscalation(esc({ ...none, is_enabled: false }))).toEqual({});
  });
});

describe("escalationTimeline", () => {
  it("lists reminder, first and cumulative second escalation", () => {
    const t = escalationTimeline(esc(), "HR Head");
    expect(t.map(s => s.day)).toEqual([1, 2, 5]);
    expect(t[2].text).toContain("HR Head");
  });
  it("omits switched-off steps and flags a missing head", () => {
    expect(escalationTimeline(esc({ reminder_after_days: 0, second_escalation_after_days: 0 })).map(s => s.day))
      .toEqual([2]);
    expect(escalationTimeline(esc())[2].text).toMatch(/not set/);
  });
});

describe("toEscalationForm", () => {
  it("maps the head to its id", () => {
    const f = toEscalationForm({ ...esc(), escalation_head: { id: "h1", name: "H", employee_id: "E", branch: "" } });
    expect(f.escalation_head).toBe("h1");
    expect(toEscalationForm({ ...esc(), escalation_head: null }).escalation_head).toBe("");
  });
});

describe("validateDelegation", () => {
  const today = "2026-11-11";
  it("accepts a valid delegation", () => {
    expect(validateDelegation(del(), today)).toEqual({});
  });
  it("requires delegate, workflow and dates", () => {
    const e = validateDelegation(del({ delegate: "", workflows: [], start_date: "", end_date: "" }), today);
    expect(Object.keys(e).sort()).toEqual(["delegate", "end_date", "start_date", "workflows"]);
  });
  it("checks date order, past end and the 180-day cap", () => {
    expect(validateDelegation(del({ end_date: "2026-11-10" }), today).end_date).toMatch(/on or after/);
    expect(validateDelegation(del({ start_date: "2026-11-01", end_date: "2026-11-05" }), today).end_date)
      .toMatch(/past/);
    expect(validateDelegation(del({ end_date: "2027-05-10" }), today).end_date).toMatch(/180/);
    expect(validateDelegation(del({ end_date: "2027-05-09" }), today)).toEqual({});   // exactly 180 days
  });
});

describe("delegation helpers", () => {
  it("counts days inclusively", () => {
    expect(daysBetweenInclusive("2026-11-11", "2026-11-11")).toBe(1);
    expect(daysBetweenInclusive("2026-03-28", "2026-03-30")).toBe(3);
  });
  it("derives the state", () => {
    const base = { revoked: false, start_date: "2026-11-10", end_date: "2026-11-12" };
    expect(delegationState(base, "2026-11-11")).toBe("active");
    expect(delegationState(base, "2026-11-09")).toBe("scheduled");
    expect(delegationState(base, "2026-11-13")).toBe("ended");
    expect(delegationState({ ...base, revoked: true }, "2026-11-11")).toBe("revoked");
  });
  it("formats the local date", () => {
    expect(localToday(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});

describe("cancellation helpers", () => {
  it("badges each status", () => {
    expect(cancellationBadge("requested")?.label).toBe("Cancellation pending");
    expect(cancellationBadge("rejected")?.cls).toBe("badge-error");
    expect(cancellationBadge("")).toBeNull();
    expect(cancellationBadge(undefined)).toBeNull();
  });
  it("validates reason and remarks", () => {
    expect(cancellationReasonError("  no ")).toBeTruthy();
    expect(cancellationReasonError("Plans changed")).toBe("");
    expect(rejectRemarksError("   ")).toBeTruthy();
    expect(rejectRemarksError("Peak season")).toBe("");
  });
});
