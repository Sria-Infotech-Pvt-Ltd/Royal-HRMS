import { describe, expect, it } from "vitest";
import type { ReportDefinition } from "@/types/reports";
import { defaultFilters, emailOmitsNotice, filtersToQuery, withQuery } from "./reportQuery";

const REPORT: ReportDefinition = {
  key: "employees", title: "Employee directory", description: "", email_omits: ["Email", "Phone"],
  filters: [{ key: "status", label: "Status", kind: "select", default: "", options: [{ value: "", label: "All" }] }],
};

describe("reportQuery", () => {
  it("starts every filter at its own default", () => {
    expect(defaultFilters(REPORT)).toEqual({ status: "" });
  });

  it("builds a query from the filters that have a value, and nothing for empty ones", () => {
    expect(filtersToQuery({ status: "active", year: "" })).toBe("status=active");
    expect(filtersToQuery({})).toBe("");
    expect(withQuery("/x/", { status: "a b" })).toBe("/x/?status=a+b");
    expect(withQuery("/x/", { status: "" })).toBe("/x/");
  });

  it("tells the sender which columns an emailed copy leaves out", () => {
    expect(emailOmitsNotice(REPORT)).toBe("The emailed copy leaves out: Email, Phone.");
    expect(emailOmitsNotice({ ...REPORT, email_omits: [] })).toBe("");
  });
});
