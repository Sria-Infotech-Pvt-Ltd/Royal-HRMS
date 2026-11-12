import { describe, expect, it } from "vitest";
import { buildApplicableLeaveTypes, buildLeaveTypesList, documentRule, type LeavePolicy } from "./_data";

const policy = (leave_type: string, over: Partial<LeavePolicy> = {}): LeavePolicy => ({
  id: 1, leave_type, leave_type_display: leave_type === "pink_leave" ? "Pink Leave" : leave_type, annual_days: 12,
  can_carry_forward: false, max_carry_forward_days: 0, policy_note: "", is_active: true, sandwich_leave_enabled: false,
  convert_to_lop: false, attachment_required: false, medical_certificate_required: false, updated_at: "", ...over,
});

describe("buildApplicableLeaveTypes (Apply Leave picker)", () => {
  const keys = (p: LeavePolicy[] | null) => buildApplicableLeaveTypes(p).map(t => t.key);

  it("hides types the employee is not eligible for (e.g. female-only Pink Leave for a man)", () => {
    const forMan = [policy("casual"), policy("paternity"), policy("maternity", { eligible_for_me: false }),
                    policy("pink_leave", { eligible_for_me: false })];
    expect(keys(forMan)).not.toContain("pink_leave");
    expect(keys(forMan)).not.toContain("maternity");
    expect(keys(forMan)).toContain("paternity");
    expect(keys(forMan)).toContain("casual");
    const forWoman = [policy("pink_leave", { eligible_for_me: true }), policy("paternity", { eligible_for_me: false })];
    expect(keys(forWoman)).toContain("pink_leave");
    expect(keys(forWoman)).not.toContain("paternity");
  });

  it("hides inactive built-ins, keeps built-ins without a policy row, and shows nothing while loading", () => {
    expect(keys([policy("paternity", { is_active: false })])).not.toContain("paternity");
    expect(keys([])).toContain("casual");
    expect(keys(null)).toEqual([]);
  });

  it("leaves the full HR list unchanged", () => {
    const all = buildLeaveTypesList([policy("maternity", { eligible_for_me: false })]).map(t => t.key);
    expect(all).toContain("maternity");
  });
});

describe("documentRule (Supporting Document required / optional)", () => {
  it("follows the leave type settings", () => {
    expect(documentRule(policy("sick"), 5, true).required).toBe(false);              // setting off -> optional
    expect(documentRule(policy("casual", { attachment_required: true }), 1, false).required).toBe(true);
    const cert = policy("sick", { medical_certificate_required: true, medical_certificate_after_days: 3 });
    expect(documentRule(cert, 2, false)).toEqual({ required: false,
      hint: "A medical certificate is required for leave of 3 or more days." });
    expect(documentRule(cert, 3, false).required).toBe(true);
    expect(documentRule(undefined, 1, true).required).toBe(true);                    // not loaded yet: built-in default
  });
});
