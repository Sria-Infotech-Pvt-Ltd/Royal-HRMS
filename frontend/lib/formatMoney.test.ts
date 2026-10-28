import { describe, expect, it } from "vitest";
import { formatRupees } from "./formatMoney";

describe("formatRupees", () => {
  it("groups digits the Indian way", () => {
    expect(formatRupees("150000")).toBe("Rs 1,50,000");
    expect(formatRupees(12345678)).toBe("Rs 1,23,45,678");
  });

  it("puts the minus sign before Rs for a negative amount", () => {
    expect(formatRupees("-150000.00")).toBe("-Rs 1,50,000");
  });

  it("shows zero plainly and a dash for a non-number", () => {
    expect(formatRupees(0)).toBe("Rs 0");
    expect(formatRupees("abc")).toBe("—");
  });
});
