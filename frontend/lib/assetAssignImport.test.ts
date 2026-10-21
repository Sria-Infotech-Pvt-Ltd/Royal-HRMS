import { describe, expect, it } from "vitest";
import { ASSET_ASSIGN_COLUMNS, ASSIGN_STATUS_LABEL, mappingText, type AssetAssignRow } from "./assetAssignImport";
import { checkImportFile, errorText } from "./assetImport";

const row = (over: Partial<AssetAssignRow> = {}): AssetAssignRow => ({
  row: 2, asset_tag: "AST-1", asset_name: "", employee_id: "EMP1", employee_name: "",
  status: "ready", errors: [], ...over,
});

describe("asset assignment import helpers", () => {
  it("lists the agreed template columns in order", () => {
    expect(ASSET_ASSIGN_COLUMNS.map(c => c.header)).toEqual([
      "Asset Tag", "Employee ID", "Assigned Date", "Condition at Assignment", "Expected Return Date", "Remarks",
    ]);
    expect(ASSET_ASSIGN_COLUMNS.filter(c => c.required).map(c => c.header)).toEqual([
      "Asset Tag", "Employee ID", "Assigned Date", "Condition at Assignment",
    ]);
  });

  it("labels every row status", () => {
    expect(ASSIGN_STATUS_LABEL.already_assigned).toBe("Already assigned");
    expect(Object.keys(ASSIGN_STATUS_LABEL).sort()).toEqual(["already_assigned", "assigned", "error", "ready"]);
  });

  it("shows resolved names when the server found them, else the file's values", () => {
    expect(mappingText(row())).toEqual({ asset: "AST-1", employee: "EMP1" });
    expect(mappingText(row({ asset_name: "Laptop", employee_name: "A. Person" })))
      .toEqual({ asset: "Laptop (AST-1)", employee: "A. Person (EMP1)" });
    expect(mappingText(row({ asset_tag: "", employee_id: "" }))).toEqual({ asset: "—", employee: "—" });
  });

  it("reuses the bulk-import file checks and error text", () => {
    expect(checkImportFile({ name: "assign.xlsx", size: 10 })).toBeNull();
    expect(checkImportFile({ name: "assign.xls", size: 10 })).toBe("Upload a .csv or .xlsx file.");
    expect(errorText([{ column: "Employee ID", message: "This employee is inactive." }]))
      .toBe("Employee ID: This employee is inactive.");
  });
});
