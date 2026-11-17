// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { SessionPayload } from "@/lib/session";

// The REAL shell (tab bar, tab switching, the timesheet view); every tab's content and the banner are stubs.
let query = "";
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(query) }));
vi.mock("@/hooks/useEmployeeDashboard", () => ({ useAttendanceStatus: () => ({ data: null, refetch: vi.fn() }) }));
vi.mock("./_components/ViewAsStrip", () => ({ default: () => <div>view-as-strip</div> }));
vi.mock("./_components/HomeBanner", () => ({ default: () => <div>banner</div> }));
vi.mock("./_components/HomeTab", () => ({ default: () => <div>home-content</div> }));
vi.mock("./_components/PoliciesAssetsTab", () => ({ default: () => <div>assets-content</div> }));
vi.mock("./_components/HrHelpTab", () => ({ default: () => <div>hrhelp-content</div> }));
vi.mock("./_components/TaxTab", () => ({ default: () => <div>tax-content</div> }));
vi.mock("./_components/ExpensesTab", () => ({ default: () => <div>expenses-content</div> }));
vi.mock("./_components/GrowthTab", () => ({ default: () => <div>growth-content</div> }));
vi.mock("./_components/AppraisalsTab", () => ({ default: () => <div>appraisals-content</div> }));
vi.mock("./_components/ProfileSummaryTab", () => ({ default: () => <div>profile-content</div> }));
vi.mock("../leave/_client", () => ({ default: () => <div>leave-content</div> }));
vi.mock("./_components/EssPayslipsTab", () => ({ default: () => <div>payslips-content</div> }));
vi.mock("./_components/MyDocumentsTab", () => ({ default: () => <div>documents-content</div> }));
vi.mock("./_components/EmploymentTab", () => ({ default: () => <div>employment-content</div> }));
vi.mock("./_components/EssRequestsTab", () => ({ default: () => <div>requests-content</div> }));
vi.mock("./_components/EssAnnouncementsTab", () => ({ default: () => <div>announcements-content</div> }));
vi.mock("./_components/EssAttendanceTab", () => ({
  default: ({ onOpenTimesheet }: { onOpenTimesheet?: (week: string) => void }) => (
    <div>attendance-content<button onClick={() => onOpenTimesheet?.("2026-11-02")}>stub-open-timesheet</button></div>
  ),
}));
vi.mock("./_components/EssTimesheetTab", () => ({
  default: ({ week, isReadOnly, onBack, onGoToWeek }: { week: string; isReadOnly: boolean; onBack: () => void; onGoToWeek: (week: string) => void }) => (
    <div data-testid="timesheet" data-week={week} data-readonly={String(isReadOnly)}>
      <button onClick={onBack}>stub-back</button><button onClick={() => onGoToWeek("2026-10-26")}>stub-go</button>
    </div>
  ),
}));

import EssShellClient from "./_client";

// The shell never reads the session, so an empty stand-in is enough (the prop is kept only for the server component).
const session = {} as SessionPayload;
const mount = (viewAsEmployee?: string) => render(<EssShellClient session={session} viewAsEmployee={viewAsEmployee} />);
const tab = (name: string) => screen.getByRole("button", { name });

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 14, 10, 0));          // Saturday 14 Nov 2026: this week's Monday is 9 Nov
  query = "";
});
afterEach(() => { vi.useRealTimers(); cleanup(); });

describe("My Workspace shell: the timesheet view", () => {
  it("opens on Home by default, with no tab of its own for the timesheet", () => {
    mount();
    expect(screen.getByText("home-content")).toBeTruthy();
    expect(screen.queryByTestId("timesheet")).toBeNull();
    expect(screen.queryByRole("button", { name: /Timesheet/i })).toBeNull();
  });

  it("a link with ?tab=timesheet&week= opens the timesheet for that week's Monday, with Attendance still highlighted", () => {
    query = "tab=timesheet&week=2026-11-04";
    mount();
    expect(screen.getByTestId("timesheet").getAttribute("data-week")).toBe("2026-11-02");
    expect(tab("Attendance").className).toContain("on");
    expect(tab("Home").className).not.toContain("on");
    expect(screen.getByText("banner")).toBeTruthy();                                   // it stays inside the workspace
  });

  it("keeps only the tab bar fixed at the top: the welcome banner scrolls away with the page", () => {
    query = "";
    mount();
    const fixedBlock = document.querySelector(".ess-sticky");
    expect(fixedBlock).not.toBeNull();
    expect(fixedBlock?.querySelector("nav[aria-label='Employee Self Service']")).not.toBeNull();   // the tabs stay fixed
    expect(fixedBlock?.textContent).not.toContain("banner");                                       // the banner does not
    expect(screen.getByText("banner")).toBeTruthy();                                                // it is still on the page
  });

  it("falls back to this week when the link's week is missing or not a date", () => {
    query = "tab=timesheet";
    const { unmount } = mount();
    expect(screen.getByTestId("timesheet").getAttribute("data-week")).toBe("2026-11-09");
    unmount();
    query = "tab=timesheet&week=nonsense";
    mount();
    expect(screen.getByTestId("timesheet").getAttribute("data-week")).toBe("2026-11-09");
  });

  it("opens from the Attendance tab for the week the card asked for, and Back returns to Attendance", () => {
    query = "tab=attendance";
    mount();
    fireEvent.click(screen.getByText("stub-open-timesheet"));
    expect(screen.getByTestId("timesheet").getAttribute("data-week")).toBe("2026-11-02");
    expect(screen.queryByText("attendance-content")).toBeNull();
    fireEvent.click(screen.getByText("stub-back"));
    expect(screen.getByText("attendance-content")).toBeTruthy();
    expect(tab("Attendance").className).toContain("on");
  });

  it("can move to another week from inside the timesheet", () => {
    query = "tab=timesheet&week=2026-11-09";
    mount();
    fireEvent.click(screen.getByText("stub-go"));
    expect(screen.getByTestId("timesheet").getAttribute("data-week")).toBe("2026-10-26");
  });

  it("clicking another tab leaves the timesheet", () => {
    query = "tab=timesheet&week=2026-11-09";
    mount();
    fireEvent.click(tab("Leave"));
    expect(screen.getByText("leave-content")).toBeTruthy();
    expect(screen.queryByTestId("timesheet")).toBeNull();
  });

  it("passes view-only down while an admin looks at someone else's workspace", () => {
    query = "tab=timesheet&week=2026-11-09";
    mount("uuid-of-someone-else");
    expect(screen.getByTestId("timesheet").getAttribute("data-readonly")).toBe("true");
  });

  it("an ordinary user's timesheet is editable", () => {
    query = "tab=timesheet&week=2026-11-09";
    mount();
    expect(screen.getByTestId("timesheet").getAttribute("data-readonly")).toBe("false");
  });
});
