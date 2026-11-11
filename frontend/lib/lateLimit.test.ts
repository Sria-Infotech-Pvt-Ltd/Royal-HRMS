import { describe, expect, it } from "vitest";
import { maximumError } from "./lateLimit";

describe("maximum late arrivals validation", () => {
  it("accepts whole numbers from 1 to 31", () => {
    expect(maximumError("5")).toBeNull();
    expect(maximumError("1")).toBeNull();
    expect(maximumError(" 31 ")).toBeNull();
  });

  it("rejects empty, zero, negative, decimals, text and too large", () => {
    expect(maximumError("")).toMatch(/Enter the maximum/);
    expect(maximumError("0")).toMatch(/at least 1/);
    expect(maximumError("-3")).toMatch(/whole number/);
    expect(maximumError("2.5")).toMatch(/whole number/);
    expect(maximumError("five")).toMatch(/whole number/);
    expect(maximumError("32")).toMatch(/at most 31/);
  });
});
