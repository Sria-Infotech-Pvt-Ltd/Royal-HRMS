import { describe, expect, it } from "vitest";
import { attendanceExportFilename, attendanceExportParams } from "./attendanceExport";

const base = { date: "2026-10-07", month: "2026-10", branch: "Surat", department: "" };

describe("attendanceExportParams", () => {
  it("day export sends only the date (unchanged daily behaviour)", () => {
    expect(attendanceExportParams({ ...base, mode: "day" })).toEqual({ date: "2026-10-07", branch: "Surat" });
  });

  it("month export sends month, never date", () => {
    const params = attendanceExportParams({ ...base, mode: "month", department: "Ops" });
    expect(params).toEqual({ month: "2026-10", branch: "Surat", department: "Ops" });
    expect(params).not.toHaveProperty("date");
  });
});

describe("attendanceExportFilename", () => {
  it("names the file by day or month", () => {
    expect(attendanceExportFilename({ ...base, mode: "day" })).toBe("attendance_2026-10-07.csv");
    expect(attendanceExportFilename({ ...base, mode: "month" }, "Surat_")).toBe("attendance_Surat_2026-10.csv");
  });
});
