import { describe, expect, it } from "vitest";
import { MARITAL_STATUS_OPTIONS, maritalStatusLabel } from "./maritalStatus";

describe("marital status", () => {
  it("offers all five statuses", () => {
    expect(MARITAL_STATUS_OPTIONS.map(option => option.label)).toEqual(["Single", "Married", "Divorced", "Widowed", "Separated"]);
  });

  it("shows a capitalised label, never the stored value", () => {
    expect(maritalStatusLabel("single")).toBe("Single");
    expect(maritalStatusLabel("SEPARATED")).toBe("Separated");
  });

  it("copes with blank and unknown values", () => {
    expect(maritalStatusLabel("")).toBe("—");
    expect(maritalStatusLabel(null)).toBe("—");
    expect(maritalStatusLabel("civil_partner")).toBe("Civil_partner");
  });
});
