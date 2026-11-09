import { describe, expect, it } from "vitest";
import { canRequestCandidates, initialBranchRequest } from "./interviewListScope";

// The server scopes candidates by the signed-in user's own branch (CandidateListCreateView.get): it ignores a `branch`
// parameter for anyone without settings.edit. These cases pin down what the browser may ask for, for each kind of user.
describe("Interview List candidate scope", () => {
  it("HR with recruitment.view but no branches.view still requests candidates, with no branch (the server applies their branch)", () => {
    const request = initialBranchRequest({ unrestricted: false, effectiveBranch: "Kondapur", branchId: null });
    expect(request).toEqual({ canFetch: true, branch: "" });
  });

  it("never sends the old bogus branch value (-1) when the branch list was unavailable", () => {
    const request = initialBranchRequest({ unrestricted: false, effectiveBranch: "Kondapur", branchId: null });
    expect(request.branch).not.toBe(-1);
  });

  it("sends the user's own branch id when the branch list was available (unchanged behaviour)", () => {
    expect(initialBranchRequest({ unrestricted: false, effectiveBranch: "Kondapur", branchId: 7 })).toEqual({ canFetch: true, branch: 7 });
  });

  it("keeps the admin's picker: unrestricted users request all branches by default", () => {
    expect(initialBranchRequest({ unrestricted: true, effectiveBranch: "", branchId: null })).toEqual({ canFetch: true, branch: "" });
  });

  it("makes NO candidate request for a restricted user with no branch (the server would not restrict them)", () => {
    expect(initialBranchRequest({ unrestricted: false, effectiveBranch: "", branchId: null })).toEqual({ canFetch: false, branch: "" });
    expect(canRequestCandidates({ unrestricted: false, effectiveBranch: "   " })).toBe(false);
  });

  it("allows a request only for an unrestricted user or one with a branch", () => {
    expect(canRequestCandidates({ unrestricted: true, effectiveBranch: "" })).toBe(true);
    expect(canRequestCandidates({ unrestricted: false, effectiveBranch: "Kondapur" })).toBe(true);
  });
});
