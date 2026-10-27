import { describe, expect, it } from "vitest";
import { buildNav, groupNav, isSection, type BarEntry } from "./navConfig";

const ADMIN_PERMISSIONS = [
  "announcements.view", "recruitment.view", "assessments.view", "facial_recognition.approve", "employees.view",
  "org_chart.view", "performance.review_team", "branches.view", "attendance.create", "payroll.view", "leave.view",
  "wfh.view", "expenses.view", "leave.approve", "documents.view", "audit.view", "email_logs.view", "settings.view",
];

const labelOf = (entry: BarEntry) => (entry.kind === "link" ? entry.item.label : entry.title);
const groupsFor = (permissions: string[]) => groupNav(buildNav(permissions));

describe("groupNav", () => {
  it("gives an admin 7 top-level entries in the agreed order", () => {
    const { bar } = groupsFor(ADMIN_PERMISSIONS);
    expect(bar.map(labelOf)).toEqual(["Dashboard", "Announcements", "Recruitment", "Workforce", "Time & Pay", "HR Ops", "System"]);
  });

  it("puts the agreed pages in each dropdown", () => {
    const menus = Object.fromEntries(
      groupsFor(ADMIN_PERMISSIONS).bar.flatMap(entry => (entry.kind === "menu" ? [[entry.title, entry.items.map(item => item.label)]] : [])),
    );
    expect(menus["Recruitment"]).toEqual(["Interview List", "Review & Onboarding", "Assessments", "Face ID Registrations"]);
    expect(menus["Workforce"]).toEqual(["Employees", "Organization Management", "Performance", "Company Codes"]);
    expect(menus["Time & Pay"]).toEqual(["Attendance", "Payroll", "Leave Management", "Work From Home", "Expenses"]);
    expect(menus["HR Ops"]).toEqual(["Approvals", "Separation & Exit", "Document Center"]);
    expect(menus["System"]).toEqual(["Reports", "Audit Log", "Email Logs", "Settings"]);
  });

  it("makes all 28 pages reachable, 3 of them newly linked in the profile menu", () => {
    const { bar, profile } = groupsFor(ADMIN_PERMISSIONS);
    const barPages = bar.flatMap(entry => (entry.kind === "link" ? [entry.item] : entry.items));
    expect(barPages.length + profile.length).toBe(28);
    expect(profile.map(item => item.label)).toEqual([
      "My Workspace", "My Attendance", "My Requests", "My Payslips", "My Assessments", "My Referrals",
    ]);
  });

  it("shows a user with no extra permissions only the pages they can reach", () => {
    const { bar, profile } = groupsFor([]);
    // HR Ops and System each have one open page, so they are plain links; every other section disappears.
    expect(bar.map(labelOf)).toEqual(["Dashboard", "Separation & Exit", "Reports"]);
    expect(bar.every(entry => entry.kind === "link")).toBe(true);
    expect(profile).toHaveLength(6);
  });

  it("hides a section with no visible pages and shows a one-page section as a plain link", () => {
    const { bar } = groupsFor(["employees.view"]);
    expect(bar.map(labelOf)).toEqual(["Dashboard", "Employees", "Separation & Exit", "Reports"]);
    expect(bar.find(entry => labelOf(entry) === "Employees")?.kind).toBe("link");
    expect(bar.some(entry => labelOf(entry) === "Recruitment")).toBe(false);
  });

  it("keeps labels, paths and permissions unchanged for existing pages", () => {
    const items = buildNav(ADMIN_PERMISSIONS).filter(entry => !isSection(entry));
    const payroll = items.find(item => "id" in item && item.id === "payroll");
    expect(payroll).toMatchObject({ label: "Payroll", path: "/dashboard/payroll", permission: "payroll.view" });
  });
});
