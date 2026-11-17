import { describe, expect, it } from "vitest";
import type { OrgUnit, Position } from "@/types/orgStructure";
import { findAttention, initialsOf, rollupUnits, vacantOf } from "./orgStructureStats";

function unit(id: string, parent: string | null, isActive = true): OrgUnit {
  return { id, name: `Unit ${id}`, code: id, parent, cost_center: "", is_active: isActive, is_department_level: false, position_count: 0, child_count: 0, created_at: "", updated_at: "" };
}

function seat(id: string, orgUnit: string, options: { holder?: boolean; chief?: boolean; active?: boolean } = {}): Position {
  return {
    id, org_unit: orgUnit, org_unit_name: "", job_template: null, job_template_name: null, title: `Seat ${id}`, grade: "",
    is_chief: options.chief ?? false, is_active: options.active ?? true,
    holder: options.holder ? `emp-${id}` : null, holder_name: options.holder ? `Person ${id}` : null, holder_employee_id: null, holder_since: null,
    scheduled: null, branch: null, branch_name: null, reports_to: null, created_at: "", updated_at: "",
  };
}

describe("rollupUnits", () => {
  const units = [unit("a", null), unit("b", "a"), unit("c", "b")];
  const positions = [
    seat("1", "a", { holder: true, chief: true }),
    seat("2", "b"),
    seat("3", "c", { holder: true }),
    seat("4", "c"),
  ];

  it("counts a unit's own seats and everything beneath it", () => {
    const rollups = rollupUnits(units, positions);
    expect(rollups.get("c")).toMatchObject({ ownTotal: 2, ownFilled: 1, total: 2, filled: 1 });
    expect(rollups.get("b")).toMatchObject({ ownTotal: 1, ownFilled: 0, total: 3, filled: 1 });
    expect(rollups.get("a")).toMatchObject({ ownTotal: 1, ownFilled: 1, total: 4, filled: 2 });
    expect(vacantOf(rollups.get("a")!)).toBe(2);
  });

  it("finds the chief seat", () => {
    expect(rollupUnits(units, positions).get("a")?.chief?.id).toBe("1");
    expect(rollupUnits(units, positions).get("b")?.chief).toBeNull();
  });

  it("ignores deactivated seats", () => {
    const rollups = rollupUnits([unit("a", null)], [seat("1", "a"), seat("2", "a", { active: false })]);
    expect(rollups.get("a")).toMatchObject({ ownTotal: 1, total: 1 });
  });

  it("does not loop forever when the data has a parent cycle", () => {
    const rollups = rollupUnits([unit("a", "b"), unit("b", "a")], [seat("1", "a")]);
    expect(rollups.size).toBeGreaterThan(0);
  });
});

describe("findAttention", () => {
  it("lists units without a chief, with a vacant chief, and empty ones", () => {
    const units = [unit("a", null), unit("b", "a"), unit("c", "a"), unit("d", "a"), unit("gone", null, false)];
    const positions = [
      seat("1", "a", { holder: true, chief: true }),
      seat("2", "b", { chief: true }),          // chief seat vacant
      seat("3", "c"),                           // seats but no chief
      seat("4", "c"),
    ];
    const attention = findAttention(units, rollupUnits(units, positions));
    expect(attention.chiefVacant.map(u => u.id)).toEqual(["b"]);
    expect(attention.withoutChief.map(u => u.id)).toEqual(["c"]);
    expect(attention.empty.map(u => u.id)).toEqual(["d"]);
    expect(attention.mostVacant[0]).toMatchObject({ vacant: 2 });
    expect(attention.mostVacant[0].unit.id).toBe("c");
  });
});

describe("initialsOf", () => {
  it("takes up to two initials", () => {
    expect(initialsOf("Asha Rao Kumar")).toBe("AR");
    expect(initialsOf("  ")).toBe("");
  });
});
