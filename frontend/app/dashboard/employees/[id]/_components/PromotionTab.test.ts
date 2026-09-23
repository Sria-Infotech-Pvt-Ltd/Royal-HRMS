import { describe, expect, it } from "vitest";
import { toPromotionRecord, type ApiPromotionRecord } from "./PromotionTab";

// Regression coverage for the production bug: a role-only change's
// Promotion History row showed "Branch Manager -> Branch Manager
// [Role change]" — the designation values shown twice, because the
// frontend had no fromRole/toRole/designationChanged fields at all and
// always displayed previous_designation/new_designation regardless of
// which field actually changed. The backend data/API were already
// correct (confirmed by inspection) — this mapper is the exact place the
// bug lived, so it's tested directly rather than through a full component
// render (this project has no DOM-emulation harness for that, per
// QuickActionChips.test.tsx's own "pure function" testing convention).

function apiRecord(overrides: Partial<ApiPromotionRecord>): ApiPromotionRecord {
  return {
    id: "rec-1",
    previous_designation: "Branch Manager",
    new_designation: "Branch Manager",
    previous_role: "hr_admin",
    new_role: "hr_admin",
    role_changed: false,
    effective_date: "2026-09-23",
    promoted_by: "Demo Corp Admin",
    ...overrides,
  };
}

describe("toPromotionRecord — role-only change", () => {
  const record = toPromotionRecord(
    apiRecord({
      previous_designation: "Branch Manager",
      new_designation: "Branch Manager",
      previous_role: "hr_admin",
      new_role: "branch_admin",
      role_changed: true,
    }),
  );

  it("marks designation as unchanged", () => {
    expect(record.designationChanged).toBe(false);
  });

  it("marks role as changed", () => {
    expect(record.roleChanged).toBe(true);
  });

  it("carries the ACTUAL previous/new role values, not the designation", () => {
    expect(record.fromRole).toBe("hr_admin");
    expect(record.toRole).toBe("branch_admin");
    // The historic bug: these must never be equal for a genuine role change.
    expect(record.fromRole).not.toBe(record.toRole);
  });

  it("still carries the (unchanged, equal) designation values for reference", () => {
    expect(record.fromDesignation).toBe("Branch Manager");
    expect(record.toDesignation).toBe("Branch Manager");
  });
});

describe("toPromotionRecord — designation-only change", () => {
  const record = toPromotionRecord(
    apiRecord({
      previous_designation: "Software Engineer",
      new_designation: "Senior Software Engineer",
      previous_role: "employee",
      new_role: "employee",
      role_changed: false,
    }),
  );

  it("marks designation as changed", () => {
    expect(record.designationChanged).toBe(true);
    expect(record.fromDesignation).toBe("Software Engineer");
    expect(record.toDesignation).toBe("Senior Software Engineer");
  });

  it("marks role as unchanged", () => {
    expect(record.roleChanged).toBe(false);
    expect(record.fromRole).toBe(record.toRole);
  });
});

describe("toPromotionRecord — role and designation changed together", () => {
  const record = toPromotionRecord(
    apiRecord({
      previous_designation: "Software Engineer",
      new_designation: "Engineering Manager",
      previous_role: "employee",
      new_role: "manager",
      role_changed: true,
    }),
  );

  it("reports both changes independently, each with its own correct values", () => {
    expect(record.designationChanged).toBe(true);
    expect(record.fromDesignation).toBe("Software Engineer");
    expect(record.toDesignation).toBe("Engineering Manager");

    expect(record.roleChanged).toBe(true);
    expect(record.fromRole).toBe("employee");
    expect(record.toRole).toBe("manager");

    // Never cross-contaminated — role values must not leak into the
    // designation fields or vice versa.
    expect(record.fromDesignation).not.toBe(record.fromRole);
    expect(record.toDesignation).not.toBe(record.toRole);
  });
});

describe("toPromotionRecord — neither actually changed (defensive)", () => {
  it("reports both as unchanged", () => {
    const record = toPromotionRecord(apiRecord({}));
    expect(record.designationChanged).toBe(false);
    expect(record.roleChanged).toBe(false);
  });
});
