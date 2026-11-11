import { describe, expect, it } from "vitest";
import { lateFormErrors, proofError, reviewTrail } from "./lateJustification";

const file = (name: string, size: number) => new File([new Uint8Array(size)], name);

describe("late justification form checks", () => {
  it("medical needs proof; other reasons don't", () => {
    expect(lateFormErrors("medical", "Fever, saw a doctor first.", null).document).toMatch(/Medical reasons need proof/);
    expect(lateFormErrors("transport", "Train was cancelled today.", null)).toEqual({});
    expect(lateFormErrors("medical", "Fever, saw a doctor first.", null, true)).toEqual({});   // resubmit keeps proof
  });

  it("explanation length", () => {
    expect(lateFormErrors("other", "late", null).explanation).toMatch(/at least 10/);
    expect(lateFormErrors("other", "x".repeat(1001), null).explanation).toMatch(/under 1000/);
  });

  it("file type and size", () => {
    expect(proofError(file("a.txt", 10))).toMatch(/PDF, JPG or PNG/);
    expect(proofError(file("a.pdf", 5 * 1024 * 1024 + 1))).toMatch(/5 MB/);
    expect(proofError(file("a.PDF", 0))).toMatch(/empty/);
    expect(proofError(file("scan.jpeg", 100))).toBeNull();
  });

  it("review trail shows who decided and why", () => {
    expect(reviewTrail({ l1_status: "approved", l1_remarks: "", l1_approver_name: "Ravi",
      l2_status: "resubmit", l2_remarks: "Upload the note", l2_approver_name: null }))
      .toEqual(["Manager (Ravi) approved", "HR asked to resubmit: Upload the note"]);
  });
});
