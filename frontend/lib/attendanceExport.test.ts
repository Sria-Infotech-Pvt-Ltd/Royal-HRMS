import { describe, expect, it } from "vitest";
import { attendanceExportFilename, attendanceExportParams, exportRangeProblem } from "./attendanceExport";

const base = {
  date: "2026-10-07", month: "2026-10", fromDate: "2026-09-25", toDate: "2026-10-05", branch: "Surat", department: "",
};

describe("attendanceExportParams", () => {
  it("day export sends only the date (unchanged daily behaviour)", () => {
    expect(attendanceExportParams({ ...base, mode: "day" })).toEqual({ date: "2026-10-07", branch: "Surat" });
  });

  it("month export sends month, never date", () => {
    const params = attendanceExportParams({ ...base, mode: "month", department: "Ops" });
    expect(params).toEqual({ month: "2026-10", branch: "Surat", department: "Ops" });
    expect(params).not.toHaveProperty("date");
  });

  it("range export sends from_date and to_date only", () => {
    expect(attendanceExportParams({ ...base, mode: "range" }))
      .toEqual({ from_date: "2026-09-25", to_date: "2026-10-05", branch: "Surat" });
  });
});

describe("attendanceExportFilename", () => {
  it("names the file by day, month or range", () => {
    expect(attendanceExportFilename({ ...base, mode: "day" })).toBe("attendance_2026-10-07.csv");
    expect(attendanceExportFilename({ ...base, mode: "month" }, "Surat_")).toBe("attendance_Surat_2026-10.csv");
    expect(attendanceExportFilename({ ...base, mode: "range" })).toBe("attendance_2026-09-25_to_2026-10-05.csv");
  });
});

describe("exportRangeProblem", () => {
  const today = "2026-10-28";

  it("accepts a valid range, a one-day range and exactly 31 days", () => {
    expect(exportRangeProblem("2026-09-25", "2026-10-05", today)).toBeNull();
    expect(exportRangeProblem("2026-10-28", "2026-10-28", today)).toBeNull();
    expect(exportRangeProblem("2026-09-01", "2026-10-01", today)).toBeNull();
  });

  it("rejects missing, reversed, future and over-31-day ranges", () => {
    expect(exportRangeProblem("", "2026-10-05", today)).toMatch(/both/i);
    expect(exportRangeProblem("2026-10-05", "2026-10-01", today)).toMatch(/on or before/);
    expect(exportRangeProblem("2026-10-20", "2026-10-29", today)).toMatch(/future/);
    expect(exportRangeProblem("2026-09-01", "2026-10-02", today)).toMatch(/31 days/);
  });
});
