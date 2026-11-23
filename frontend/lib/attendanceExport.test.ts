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

describe("single-employee export", () => {
  it("sends the exact employee ID with each period and drops branch / department", () => {
    const one = { ...base, department: "Ops", employeeId: "RIST0308G" };
    expect(attendanceExportParams({ ...one, mode: "day" })).toEqual({ date: "2026-10-07", employee: "RIST0308G" });
    expect(attendanceExportParams({ ...one, mode: "month" })).toEqual({ month: "2026-10", employee: "RIST0308G" });
    expect(attendanceExportParams({ ...one, mode: "range" }))
      .toEqual({ from_date: "2026-09-25", to_date: "2026-10-05", employee: "RIST0308G" });
  });

  it("names the file by employee and period", () => {
    expect(attendanceExportFilename({ ...base, mode: "month", employeeId: "RIST0308G" }, "Surat_"))
      .toBe("attendance_RIST0308G_2026-10.csv");
    expect(attendanceExportFilename({ ...base, mode: "day", employeeId: "A/1 2" })).toBe("attendance_A_1_2_2026-10-07.csv");
  });

  it("an empty employee ID keeps the all-employees export", () => {
    expect(attendanceExportParams({ ...base, mode: "month", employeeId: "" })).toEqual({ month: "2026-10", branch: "Surat" });
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
