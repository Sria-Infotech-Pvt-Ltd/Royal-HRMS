import { describe, expect, it } from "vitest";
import { approvalSectionsFor, sectionFromLink, type ApprovalAccess } from "./approvalSections";

const NONE: ApprovalAccess = { canApprove: false, canApproveAttendance: false, canApproveTimesheets: false, canSeePersonnel: false, canApproveFace: false };
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

  it("gives the Timesheets tab to people who can approve timesheets, and only them", () => {
    expect(keys({ ...NONE, canApproveTimesheets: true })).toEqual(["overview", "timesheets"]);
    expect(keys({ ...NONE, canApprove: true, canApproveAttendance: true })).not.toContain("timesheets");
  });

  it("names and icons the Timesheets tab", () => {
    const tab = approvalSectionsFor({ ...NONE, canApproveTimesheets: true }).find(section => section.key === "timesheets");
    expect(tab).toEqual({ key: "timesheets", label: "Timesheets", icon: "ti-clock-check" });
  });

  it("shows Face Registration only to people who can approve it, never as a side effect of leave approval", () => {
    expect(keys({ ...NONE, canApprove: true })).not.toContain("face_registration");
  });

  it("puts My Approvals first and keeps the existing tab order, with Timesheets after Attendance", () => {
    expect(keys({ canApprove: true, canApproveAttendance: true, canApproveTimesheets: true, canSeePersonnel: true, canApproveFace: true }))
      .toEqual(["overview", "approvals", "attendance", "timesheets", "personnel", "face_registration"]);
  });
});

describe("sectionFromLink", () => {
  const sections = approvalSectionsFor({ ...NONE, canApprove: true, canApproveTimesheets: true });
  it("opens the tab a link names, when the person has it", () => {
    expect(sectionFromLink("timesheets", sections)).toBe("timesheets");
    expect(sectionFromLink("approvals", sections)).toBe("approvals");
  })
  it("never opens a tab the person does not have", () => {
    expect(sectionFromLink("timesheets", approvalSectionsFor({ ...NONE, canApprove: true }))).toBeNull();
    expect(sectionFromLink("face_registration", sections)).toBeNull();
  })
  it("ignores a missing or unknown request", () => {
    expect(sectionFromLink(null, sections)).toBeNull();
    expect(sectionFromLink("", sections)).toBeNull();
    expect(sectionFromLink("nonsense", sections)).toBeNull();
  })
  it("has nothing to open for someone with no approval tabs", () => {
    expect(sectionFromLink("timesheets", approvalSectionsFor(NONE))).toBeNull();
  })
})
