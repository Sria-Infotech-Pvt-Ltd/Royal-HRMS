import { describe, expect, it } from "vitest";
import { approvalFieldError, usablePan } from "./onboardingApproval";

describe("usablePan", () => {
  it("sends a real PAN in upper case", () => {
    expect(usablePan("abcde1234f")).toBe("ABCDE1234F");
  });

  it("leaves out the masked PAN the approval screen receives (the stored PAN is kept by the server)", () => {
    expect(usablePan("ABCDE••••F")).toBe("");
    expect(usablePan("ABCDE****F")).toBe("");
    expect(usablePan("")).toBe("");
    expect(usablePan(undefined)).toBe("");
  });
});

describe("approvalFieldError", () => {
  it("does not treat a masked PAN as an error (this used to block every approval)", () => {
    expect(approvalFieldError("", "ABCDE••••F")).toBeNull();
    expect(approvalFieldError(undefined, "ABCDE••••F")).toBeNull();
  });

  it("accepts blank and valid values", () => {
    expect(approvalFieldError("", "")).toBeNull();
    expect(approvalFieldError("123456789012", "ABCDE1234F")).toBeNull();
  });

  it("still rejects a real malformed PAN or a UAN of the wrong length", () => {
    expect(approvalFieldError("", "ABC123")).toMatch(/valid PAN/);
    expect(approvalFieldError("12345", "")).toMatch(/UAN/);
  });
});
