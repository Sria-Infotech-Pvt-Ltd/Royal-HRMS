import { describe, expect, it } from "vitest";
import type { ApprovalItem, ApprovalKind, DisplayStatus } from "@/app/dashboard/approvals/_data";
import { KIND_SCOPE_NOTES, summariseTeamApprovals } from "./approvalOverview";

function item(kind: ApprovalKind, displayStatus: DisplayStatus, canAction: boolean): ApprovalItem {
  return {
    key: `${kind}:${Math.random()}`, kind, id: "1", employeeName: "A", employeeCode: "E1", status: displayStatus, displayStatus,
    submittedAt: "", detailPrimary: "", detailSecondary: "", canAction,
    raw: {} as ApprovalItem["raw"], // the counts never read the raw record
  };
}

describe("summariseTeamApprovals", () => {
  it("counts only pending requests, per kind, and separates the ones this person can act on", () => {
    const counts = summariseTeamApprovals([
      item("leave", "pending", true), item("leave", "pending", false), item("leave", "approved", true),
      item("wfh", "pending", true), item("expense", "rejected", false),
    ]);
    const by = Object.fromEntries(counts.map(count => [count.kind, count]));
    expect(by.leave).toMatchObject({ pending: 2, needsMyAction: 1 });
    expect(by.wfh).toMatchObject({ pending: 1, needsMyAction: 1 });
    expect(by.expense).toMatchObject({ pending: 0, needsMyAction: 0 });
  });

  it("never counts a request that is not in the list it was given (no leaking across scopes)", () => {
    expect(summariseTeamApprovals([]).every(count => count.pending === 0 && count.needsMyAction === 0)).toBe(true);
  });

  it("describes a scope for every workflow, and does not claim they are identical", () => {
    const notes = Object.values(KIND_SCOPE_NOTES);
    expect(notes.every(note => note.length > 0)).toBe(true);
    expect(new Set(notes).size).toBeGreaterThan(1);
  });
});
