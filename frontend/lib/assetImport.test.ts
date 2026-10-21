import { describe, expect, it } from "vitest";
import { ASSET_IMPORT_COLUMNS, checkImportFile, decodeReport, errorText } from "./assetImport";

describe("checkImportFile", () => {
  it("accepts csv and xlsx within 5 MB", () => {
    expect(checkImportFile({ name: "assets.CSV", size: 10 })).toBeNull();
    expect(checkImportFile({ name: "assets.xlsx", size: 10 })).toBeNull();
  });
  it("rejects other types, empty and oversize files", () => {
    expect(checkImportFile({ name: "assets.xls", size: 10 })).toMatch(/\.csv or \.xlsx/);
    expect(checkImportFile({ name: "a.csv", size: 0 })).toMatch(/empty/);
    expect(checkImportFile({ name: "a.csv", size: 6 * 1024 * 1024 })).toMatch(/5 MB/);
  });
});

describe("errorText / decodeReport", () => {
  it("joins row errors with their column", () => {
    expect(errorText([{ column: "Branch", message: "Unknown." }, { column: "", message: "Other." }]))
      .toBe("Branch: Unknown. · Other.");
  });
  it("decodes the base64 CSV report", () => {
    const b64 = btoa("Row,Asset Tag\n2,X\n");
    expect(new TextDecoder().decode(decodeReport(b64))).toBe("Row,Asset Tag\n2,X\n");
  });
});

describe("ASSET_IMPORT_COLUMNS", () => {
  it("lists the five required columns", () => {
    expect(ASSET_IMPORT_COLUMNS.filter(c => c.required).map(c => c.header))
      .toEqual(["Asset Tag", "Asset Name", "Category", "Asset Type", "Branch"]);
  });
});
