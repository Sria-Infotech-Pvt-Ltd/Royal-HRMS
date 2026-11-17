import { describe, expect, it } from "vitest";
import type { OrgUnit, Position } from "@/types/orgStructure";
import { buildPositionsCsv, csvCell } from "./orgExport";

function unit(id: string, name: string, parent: string | null): OrgUnit {
  return { id, name, code: id, parent, cost_center: "", is_active: true, is_department_level: false, position_count: 0, child_count: 0, created_at: "", updated_at: "" };
}
function seat(id: string, orgUnit: string, title: string, extra: Partial<Position> = {}): Position {
  return {
    id, org_unit: orgUnit, org_unit_name: "", job_template: null, job_template_name: null, title, grade: "", is_chief: false, is_active: true,
    holder: null, holder_name: null, holder_employee_id: null, holder_since: null, scheduled: null, branch: null, branch_name: null,
    reports_to: null, created_at: "", updated_at: "", ...extra,
  };
}

describe("csvCell", () => {
  it("quotes values with commas, quotes and line breaks", () => {
    expect(csvCell("Rao, Asha")).toBe('"Rao, Asha"');
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
    expect(csvCell("plain")).toBe("plain");
  });
  it("turns anything a spreadsheet would run as a formula into plain text", () => {
    expect(csvCell("=SUM(A1)")).toBe("'=SUM(A1)");
    expect(csvCell("@cmd")).toBe("'@cmd");
  });
});

describe("buildPositionsCsv", () => {
  it("writes one row per position with its unit path, status and holder", () => {
    const units = [unit("a", "Company", null), unit("b", "Finance", "a")];
    const csv = buildPositionsCsv(units, [
      seat("1", "b", "Accountant", { holder: "e1", holder_name: "Asha Rao", holder_employee_id: "E001", reports_to: { position_id: "2", title: "Finance Head", holder_name: null } }),
      seat("2", "b", "Finance Head", { is_chief: true }),
      seat("3", "b", "Old role", { is_active: false }),
    ]).split("\r\n");
    expect(csv[0]).toBe("Org unit,Unit path,Position,Grade,Head of unit,Status,Holder,Employee ID,Branch,Reports to");
    expect(csv).toContain("Finance,Company > Finance,Accountant,,,Filled,Asha Rao,E001,,Finance Head");
    expect(csv).toContain("Finance,Company > Finance,Finance Head,,Yes,Vacant,,,,");
    expect(csv).toContain("Finance,Company > Finance,Old role,,,Inactive,,,,");
    expect(csv).toHaveLength(4);
  });
});
