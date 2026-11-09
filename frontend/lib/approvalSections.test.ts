import { describe, expect, it } from "vitest";
import { approvalSectionsFor, type ApprovalAccess } from "./approvalSections";

const NONE: ApprovalAccess = { canApprove: false, canApproveAttendance: false, canSeePersonnel: false, canApproveFace: false };
const keys = (access: ApprovalAccess) => approvalSectionsFor(access).map(section => section.key);

describe("approvalSectionsFor", () => {
  it("shows nothing to someone who approves nothing", () => {
    expect(keys(NONE)).toEqual([]);
  });

  it("lets a user with only facial_recognition.approve reach the Face Registration tab", () => {
    expect(keys({ ...NONE, canApproveFace: true })).toEqual(["overview", "face_registration"]);
  });

  it("keeps each existing tab gated by its own permission", () => {
    expect(keys({ ...NONE, canApprove: true })).toEqual(["overview", "approvals"]);
    expect(keys({ ...NONE, canApproveAttendance: true })).toEqual(["overview", "attendance"]);
    expect(keys({ ...NONE, canSeePersonnel: true })).toEqual(["overview", "personnel"]);
  });

  it("shows Face Registration only to people who can approve it, never as a side effect of leave approval", () => {
    expect(keys({ ...NONE, canApprove: true })).not.toContain("face_registration");
  });

  it("puts My Approvals first and keeps the existing tab order", () => {
    expect(keys({ canApprove: true, canApproveAttendance: true, canSeePersonnel: true, canApproveFace: true }))
      .toEqual(["overview", "approvals", "attendance", "personnel", "face_registration"]);
  });
});
