import { describe, expect, it } from "vitest";
import { reportFormError, reviewError, wfhMedicalProofError, WFH_PROOF_MAX_BYTES } from "./wfhReport";

describe("wfhMedicalProofError", () => {
  it("needs a PDF/JPG/PNG up to 5 MB only for medical WFH", () => {
    expect(wfhMedicalProofError(false, null)).toBeNull();
    expect(wfhMedicalProofError(true, null)).toMatch(/Attach/);
    expect(wfhMedicalProofError(true, { size: 100, type: "application/pdf" })).toBeNull();
    expect(wfhMedicalProofError(true, { size: 100, type: "text/plain" })).toMatch(/PDF, JPG or PNG/);
    expect(wfhMedicalProofError(true, { size: WFH_PROOF_MAX_BYTES + 1, type: "image/png" })).toMatch(/5 MB/);
  });
});

describe("report and review checks", () => {
  it("needs completed work", () => {
    expect(reportFormError("  ")).toMatch(/Describe/);
    expect(reportFormError("Closed 3 tickets")).toBeNull();
  });

  it("needs an outcome, and a reason for Not accepted", () => {
    expect(reviewError("", "")).toMatch(/Choose/);
    expect(reviewError("half_day", "")).toBeNull();
    expect(reviewError("not_accepted", "")).toMatch(/reason/);
    expect(reviewError("not_accepted", "No report content")).toBeNull();
  });
});
