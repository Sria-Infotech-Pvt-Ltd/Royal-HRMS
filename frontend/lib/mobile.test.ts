import { describe, expect, it } from "vitest";
import { MOBILE_ERROR, mobileError, normaliseMobile } from "./mobile";

describe("mobile rule", () => {
  it("accepts a 10-digit Indian mobile in any common format", () => {
    for (const value of ["9876543210", "+91 98765 43210", "91-9876543210", "98765 43210"]) {
      expect(normaliseMobile(value)).toBe("9876543210");
      expect(mobileError(value)).toBeNull();
    }
  });

  it("rejects 123, short, long, wrong first digit and letters, with the friendly message", () => {
    for (const value of ["123", "98765", "98765432101234", "5876543210", "abcdefghij"]) {
      expect(normaliseMobile(value)).toBeNull();
      expect(mobileError(value)).toBe(MOBILE_ERROR);
    }
  });

  it("treats blank as valid so optional fields can stay empty", () => {
    expect(mobileError("   ")).toBeNull();
  });
});
