// Which candidate request the Interview List may make, for people who are not allowed to see every branch.
//
// The candidate list endpoint (CandidateListCreateView.get) scopes by the AUTHENTICATED user, not by what the browser asks
// for: for anyone without settings.edit who has a branch, the server returns only candidates of that branch and ignores a
// `branch` parameter. So an HR user who may view recruitment but not the branch list (no branches.view) can safely
// request candidates without choosing a branch: the server applies their own branch. The browser never filters.
//
// One case stays closed on the browser side too: a restricted user with NO branch. The server does not restrict a user
// whose branch is blank, so the browser must not send a request for them at all.
export interface BranchScopeInput {
  /** settings.edit holders and superusers: the branch picker is theirs to use. */
  unrestricted: boolean;
  /** The signed-in user's own branch name ("" for unrestricted users or when none is set). */
  effectiveBranch: string;
}

/** False for a restricted user with no branch: no candidate request is made for them. */
export function canRequestCandidates({ unrestricted, effectiveBranch }: BranchScopeInput): boolean {
  return unrestricted || effectiveBranch.trim() !== "";
}

export interface InitialBranchRequest {
  canFetch: boolean;
  /** The `branch` value to send: a real branch id, or "" to send none and let the server apply the user's own scope. */
  branch: number | "";
}

/** The first request: `branchId` is the id of the user's own branch when the branch list was available, else null. */
export function initialBranchRequest(input: BranchScopeInput & { branchId: number | null }): InitialBranchRequest {
  if (!canRequestCandidates(input)) return { canFetch: false, branch: "" };
  if (input.unrestricted) return { canFetch: true, branch: "" };
  return { canFetch: true, branch: input.branchId ?? "" };
}
