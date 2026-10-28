import { describe, expect, it } from "vitest";
import { eligibleAmount } from "./taxDeclarationForm";

describe("eligible amount", () => {
  it("caps a declared amount at its limit (the reported 80D case: 70,000 declared, 50,000 counts)", () => {
    expect(eligibleAmount(70000, 50000)).toBe(50000);
  });
  it("leaves an amount under its limit, or with no limit, alone", () => {
    expect(eligibleAmount(30000, 50000)).toBe(30000);
    expect(eligibleAmount(70000, null)).toBe(70000);
  });
});
