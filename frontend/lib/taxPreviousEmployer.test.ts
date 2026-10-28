import { describe, expect, it } from "vitest";
import { PREVIOUS_TDS_ERROR, previousEmployerTdsError } from "./taxPreviousEmployer";

describe("previous employer TDS", () => {
  it("rejects the reported case: income 100 with TDS 500", () => {
    expect(previousEmployerTdsError("100", "500")).toBe(PREVIOUS_TDS_ERROR);
  });
  it("accepts TDS equal to or below the income, and blanks", () => {
    expect(previousEmployerTdsError("100", "100")).toBeNull();
    expect(previousEmployerTdsError("1000", "50")).toBeNull();
    expect(previousEmployerTdsError("", "")).toBeNull();
  });
  it("rejects TDS with no income entered", () => {
    expect(previousEmployerTdsError("", "10")).toBe(PREVIOUS_TDS_ERROR);
  });
});
