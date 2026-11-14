// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

// The REAL page (tab bar, link handling); the permission lookups and every tab's content are stubs.
let query = "";
let permissions: Set<string>;
let user: { can_manage_team: boolean; is_superuser: boolean } | null;

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(query) }));
vi.mock("@/hooks/usePermission", () => ({
  usePermission: (code: string) => permissions.has(code),
  useAnyPermission: (...codes: string[]) => codes.some(code => permissions.has(code)),
}));
vi.mock("@/hooks/useCurrentUser", () => ({ useCurrentUser: () => user }));
vi.mock("./_components/TeamApprovalsSection", () => ({ default: () => <div>team-approvals-content</div> }));
vi.mock("./_components/AttendanceApprovalTab", () => ({ default: () => <div>attendance-content</div> }));
vi.mock("./_components/FaceRegistrationApprovalsTab", () => ({ default: () => <div>face-content</div> }));
vi.mock("./_components/PersonnelActionsTab", () => ({ default: () => <div>personnel-content</div> }));
vi.mock("./_components/TimesheetApprovalsTab", () => ({ default: () => <div>timesheets-content</div> }));
vi.mock("./_components/MyApprovalsOverview", () => ({ default: () => <div>overview-content</div> }));

import ApprovalsPage from "./page";

beforeEach(() => { query = ""; permissions = new Set(); user = { can_manage_team: false, is_superuser: false }; });
afterEach(() => cleanup());

describe("Approvals page: opening a tab from a link", () => {
  it("opens on My Approvals by default", () => {
    permissions = new Set(["timesheet.approve"]);
    render(<ApprovalsPage />);
    expect(screen.getByText("overview-content")).toBeTruthy();
    expect(screen.queryByText("timesheets-content")).toBeNull();
  });

  it("?section=timesheets opens the Timesheets tab for someone who can approve timesheets (a bell notice's link)", () => {
    query = "section=timesheets";
    permissions = new Set(["timesheet.approve"]);
    render(<ApprovalsPage />);
    expect(screen.getByText("timesheets-content")).toBeTruthy();
    expect(screen.queryByText("overview-content")).toBeNull();
    expect(screen.getByRole("button", { name: /Timesheets/ }).className).toContain("active");
  });

  it("works for an assigned manager with no approval permission, and for a superuser", () => {
    query = "section=timesheets";
    user = { can_manage_team: true, is_superuser: false };
    const { unmount } = render(<ApprovalsPage />);
    expect(screen.getByText("timesheets-content")).toBeTruthy();
    unmount();
    user = { can_manage_team: false, is_superuser: true };
    render(<ApprovalsPage />);
    expect(screen.getByText("timesheets-content")).toBeTruthy();
  });

  it("does not open a tab the person does not have: they stay on My Approvals", () => {
    query = "section=timesheets";
    permissions = new Set(["facial_recognition.approve"]);
    render(<ApprovalsPage />);
    expect(screen.queryByText("timesheets-content")).toBeNull();
    expect(screen.getByText("overview-content")).toBeTruthy();
  });

  it("ignores an unknown section name", () => {
    query = "section=nonsense";
    permissions = new Set(["timesheet.approve"]);
    render(<ApprovalsPage />);
    expect(screen.getByText("overview-content")).toBeTruthy();
  });
});
