import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

// No network in these tests — the modals only call the API on user actions.
vi.mock("@/lib/clientApi", () => ({ default: { post: vi.fn(), get: vi.fn() } }));
vi.mock("@/lib/downloadFile", () => ({ downloadBlobFile: vi.fn() }));

import AdjustmentImportModal from "./AdjustmentImportModal";
import SalaryStructureImportModal from "@/app/dashboard/settings/payroll-config/_components/SalaryStructureImportModal";
import { API } from "@/lib/api/endpoints";

const noop = () => {};

describe("Salary setup import (mode salaries)", () => {
  const html = renderToStaticMarkup(<SalaryStructureImportModal mode="salaries" onClose={noop} onImported={noop} />);

  it("offers both sample formats and a preview step", () => {
    expect(html).toContain("Import Salaries");
    expect(html).toContain("Download Sample CSV");
    expect(html).toContain("Download Sample Excel");
    expect(html).toContain("Preview");
    expect(html).toContain("Nothing is saved until you confirm");
  });

  it("asks before replacing a revision with the same date", () => {
    expect(html).toContain("Replace revisions with the same Effective From");
    expect(html).not.toContain("Update existing structures");
  });

  it("explains that history and structures are kept", () => {
    expect(html).toContain("earlier revisions stay as history");
    expect(html).toContain("salary structures are not changed");
  });

  it("uses its own endpoints", () => {
    expect(API.payroll.salaryImport).toBe("/payroll/salary-import/");
    expect(API.payroll.salaryImportSample).toBe("/payroll/salary-import/sample/");
  });
});

describe("Existing structure import modes are unchanged", () => {
  it("structures mode still offers Update existing structures, not Replace", () => {
    const html = renderToStaticMarkup(<SalaryStructureImportModal mode="structures" onClose={noop} onImported={noop} />);
    expect(html).toContain("Import Salary Structures");
    expect(html).toContain("Update existing structures");
    expect(html).not.toContain("Replace revisions with the same Effective From");
  });

  it("assign mode shows neither option", () => {
    const html = renderToStaticMarkup(<SalaryStructureImportModal mode="assign" onClose={noop} onImported={noop} />);
    expect(html).toContain("Assign Structures to Employees");
    expect(html).not.toContain("Update existing structures");
    expect(html).not.toContain("Replace revisions");
  });
});

describe("Adjustments import", () => {
  const html = renderToStaticMarkup(
    <AdjustmentImportModal month="2026-01" monthLabel="January 2026" onClose={noop} onImported={noop} />,
  );

  it("names the payroll month and is all-or-nothing", () => {
    expect(html).toContain("Import Adjustments — January 2026");
    expect(html).toContain("nothing is saved if any row has an error");
  });

  it("offers both sample formats", () => {
    expect(html).toContain("Download Sample CSV");
    expect(html).toContain("Download Sample Excel");
    expect(API.payroll.adjustmentsImportSample).toBe("/payroll/adjustments/bulk-import/sample/");
  });
});
