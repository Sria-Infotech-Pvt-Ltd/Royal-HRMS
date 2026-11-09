import { describe, expect, it } from "vitest";
import { REJECTION_REASON_REQUIRED, rejectionProblem } from "./faceRejection";

describe("rejectionProblem", () => {
  it("refuses an empty or whitespace-only reason", () => {
    expect(rejectionProblem("")).toBe(REJECTION_REASON_REQUIRED);
    expect(rejectionProblem("   \n ")).toBe(REJECTION_REASON_REQUIRED);
  });

  it("accepts a written reason", () => {
    expect(rejectionProblem("The photo was too dark.")).toBe("");
  });
});
