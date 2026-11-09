import { describe, expect, it } from "vitest";
import { buildNav, groupNav, isSection, profileMenuItems, withHomeLinks, withTeamLink, workspaceNav, type BarEntry } from "./navConfig";

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

  it("makes all 29 pages reachable, 3 of them newly linked in the profile menu", () => {
    const { bar, profile } = groupsFor(ADMIN_PERMISSIONS);
    const barPages = bar.flatMap(entry => (entry.kind === "link" ? [entry.item] : entry.items));
    expect(barPages.length + profile.length).toBe(29);
    expect(profile.map(item => item.label)).toEqual([
      "My Workspace", "My Attendance", "My Requests", "My Payslips", "My Assessments", "My Referrals", "My Interviews",
    ]);
  });

  it("shows a user with no extra permissions only the pages they can reach", () => {
    const { bar, profile } = groupsFor([]);
    // HR Ops has one open page, so it is a plain link; every other section disappears. Reports needs a report permission.
    expect(bar.map(labelOf)).toEqual(["Dashboard", "Separation & Exit"]);
    expect(bar.every(entry => entry.kind === "link")).toBe(true);
    expect(profile).toHaveLength(7);
  });

  it("hides a section with no visible pages and shows a one-page section as a plain link", () => {
    const { bar } = groupsFor(["employees.view"]);
    expect(bar.map(labelOf)).toEqual(["Dashboard", "Employees", "Separation & Exit"]);
    expect(bar.find(entry => labelOf(entry) === "Employees")?.kind).toBe("link");
    expect(bar.some(entry => labelOf(entry) === "Recruitment")).toBe(false);
  });

  it("keeps labels, paths and permissions unchanged for existing pages", () => {
    const items = buildNav(ADMIN_PERMISSIONS).filter(entry => !isSection(entry));
    const payroll = items.find(item => "id" in item && item.id === "payroll");
    expect(payroll).toMatchObject({ label: "Payroll", path: "/dashboard/payroll", permission: "payroll.view" });
  });

  it("shows Approvals to someone whose only approval permission is Face ID, and not to someone with none", () => {
    const hasApprovals = (permissions: string[]) => buildNav(permissions).some(entry => !isSection(entry) && entry.id === "approvals");
    expect(hasApprovals(["facial_recognition.approve"])).toBe(true);
    expect(hasApprovals(["leave.approve"])).toBe(true);        // existing behaviour unchanged
    expect(hasApprovals(["leave.view"])).toBe(false);
  });
});

// What the top bar shows on the employee-style workspace: only the modules a person's permissions add.
const EMPLOYEE_PERMISSIONS = [
  "documents.view", "expenses.create", "expenses.view", "leave.create", "leave.view", "org_chart.view",
  "payroll.view_own", "referrals.create", "referrals.view", "wfh.create", "wfh.view",
];
const SAMREEN_HR_PERMISSIONS = [
  ...EMPLOYEE_PERMISSIONS, "leave.approve", "employees.view", "employees.edit", "recruitment.view", "recruitment.edit",
  "onboarding.approve", "facial_recognition.approve",
];
const VIGNESH_MANAGER_PERMISSIONS = [...EMPLOYEE_PERMISSIONS, "leave.approve"];

const workspaceBar = (permissions: string[]) => workspaceNav(permissions).bar;
const pagesIn = (bar: BarEntry[]) => bar.flatMap(entry => (entry.kind === "link" ? [entry.item.label] : entry.items.map(item => item.label)));

describe("workspaceNav", () => {
  it("adds nothing for an ordinary employee: their navigation is unchanged", () => {
    expect(workspaceBar(EMPLOYEE_PERMISSIONS)).toEqual([]);
  });

  it("gives HR their modules, and only the ones their permissions allow", () => {
    const pages = pagesIn(workspaceBar(SAMREEN_HR_PERMISSIONS));
    expect(pages).toEqual(expect.arrayContaining(["Interview List", "Review & Onboarding", "Face ID Registrations", "Employees", "Approvals"]));
    for (const unauthorized of ["Payroll", "Settings", "Attendance", "Company Codes", "Audit Log", "Announcements"]) {
      expect(pages, unauthorized).not.toContain(unauthorized);
    }
  });

  it("keeps self-service pages (Leave, Expenses, Documents, ...) out of the workspace bar: the tabs already cover them", () => {
    const pages = pagesIn(workspaceBar(SAMREEN_HR_PERMISSIONS));
    for (const selfService of ["Leave", "Leave Management", "Expenses", "Document Center", "Work From Home", "Organization Management", "Dashboard"]) {
      expect(pages, selfService).not.toContain(selfService);
    }
  });

  it("gives a manager Approvals and nothing HR-only", () => {
    expect(pagesIn(workspaceBar(VIGNESH_MANAGER_PERMISSIONS))).toEqual(["Approvals", "Reports"]);   // Reports: the leave report
  });

  it("shows nothing for permissions a person does not hold", () => {
    expect(pagesIn(workspaceBar([...EMPLOYEE_PERMISSIONS, "facial_recognition.approve"]))).toEqual(["Face ID Registrations", "Approvals", "Reports"]);
  });
});

describe("withTeamLink", () => {
  const fullBar = (permissions: string[]) => groupNav(buildNav(permissions)).bar;

  it("gives a team manager one Dashboard link (their own), in place of the generic one", () => {
    const labels = withTeamLink(fullBar(VIGNESH_MANAGER_PERMISSIONS), true).map(labelOf);
    expect(labels.filter(label => label === "Dashboard")).toHaveLength(1);
    expect(labels[0]).toBe("Dashboard");
    const dashboard = withTeamLink(fullBar(VIGNESH_MANAGER_PERMISSIONS), true)[0];
    expect(dashboard.kind === "link" && dashboard.item.path).toBe("/dashboard/team");
  });

  it("keeps a superuser's Dashboard (the Workforce dashboard) and adds Manager Dashboard after it", () => {
    const labels = withTeamLink(fullBar(VIGNESH_MANAGER_PERMISSIONS), true, { keepDashboard: true }).map(labelOf);
    expect(labels.slice(0, 2)).toEqual(["Dashboard", "Manager Dashboard"]);
  });

  it("adds Manager Dashboard to a workspace bar that has no Dashboard link", () => {
    expect(withTeamLink(workspaceBar(VIGNESH_MANAGER_PERMISSIONS), true).map(labelOf)).toEqual(["Dashboard", "Approvals", "Reports"]);
  });

  it("does not add it, or drop Dashboard, for anyone who is not a team manager", () => {
    const bar = fullBar(EMPLOYEE_PERMISSIONS);
    expect(withTeamLink(bar, false)).toBe(bar);
    expect(withTeamLink(workspaceBar(SAMREEN_HR_PERMISSIONS), false).map(labelOf)).not.toContain("Dashboard");
  });
});

describe("withHomeLinks", () => {
  const fullBar = (permissions: string[]) => groupNav(buildNav(permissions)).bar;

  it("gives an HR user HR Dashboard at the front of the bar, replacing the single Dashboard link", () => {
    const bar = withHomeLinks(fullBar(SAMREEN_HR_PERMISSIONS), { hasHrDashboard: true, isSuperuser: false });
    expect(bar.map(labelOf)[0]).toBe("HR Dashboard");
    expect(bar.map(labelOf)).not.toContain("Dashboard");
    expect(pagesIn(bar)).toEqual(expect.arrayContaining(["Employees", "Approvals", "Interview List"]));   // HR modules stay
  });

  it("keeps My Workspace out of the top bar: it is in the profile menu and the dashboard banner", () => {
    for (const bar of [withHomeLinks(fullBar(SAMREEN_HR_PERMISSIONS), { hasHrDashboard: true, isSuperuser: false }),
                       withHomeLinks(workspaceBar(SAMREEN_HR_PERMISSIONS), { hasHrDashboard: true, isSuperuser: false })]) {
      expect(pagesIn(bar)).not.toContain("My Workspace");
    }
    const menu = profileMenuItems(groupNav(buildNav(SAMREEN_HR_PERMISSIONS)).profile, { homeIsWorkspace: true, isTeamManager: false });
    expect(menu.map(item => item.label)).toContain("My Workspace");
  });

  it("points HR Dashboard at the HR dashboard route", () => {
    const bar = withHomeLinks(workspaceBar(SAMREEN_HR_PERMISSIONS), { hasHrDashboard: true, isSuperuser: false });
    const link = bar.find(entry => entry.kind === "link" && entry.item.label === "HR Dashboard");
    expect(link && link.kind === "link" && link.item.path).toBe("/dashboard/hr");
  });

  it("does not touch the bar of a manager, an employee or a superuser", () => {
    for (const permissions of [VIGNESH_MANAGER_PERMISSIONS, EMPLOYEE_PERMISSIONS]) {
      const bar = fullBar(permissions);
      expect(withHomeLinks(bar, { hasHrDashboard: false, isSuperuser: false })).toBe(bar);
      expect(pagesIn(withHomeLinks(bar, { hasHrDashboard: false, isSuperuser: false }))).not.toContain("HR Dashboard");
    }
    const adminBar = fullBar(ADMIN_PERMISSIONS);
    expect(withHomeLinks(adminBar, { hasHrDashboard: true, isSuperuser: true })).toBe(adminBar);
  });

  it("keeps Team right after HR Dashboard for someone who is both HR and a team manager", () => {
    const bar = withTeamLink(withHomeLinks(workspaceBar(SAMREEN_HR_PERMISSIONS), { hasHrDashboard: true, isSuperuser: false }), true);
    expect(bar.map(labelOf).slice(0, 2)).toEqual(["HR Dashboard", "Manager Dashboard"]);
  });
});

describe("Reports navigation", () => {
  const hasReports = (permissions: string[]) => buildNav(permissions).some(entry => !isSection(entry) && entry.id === "reports");

  it("shows Reports only to someone who can run at least one report", () => {
    expect(hasReports(EMPLOYEE_PERMISSIONS)).toBe(false);
    expect(hasReports(["employees.view"])).toBe(false);
    for (const permission of ["employees.export", "attendance.view", "leave.approve", "wfh.approve", "separation.approve", "facial_recognition.approve", "recruitment.view", "reports.view"]) {
      expect(hasReports([...EMPLOYEE_PERMISSIONS, permission]), permission).toBe(true);
    }
  });

  it("puts Reports in the workspace top bar for HR and managers, never for an employee", () => {
    expect(pagesIn(workspaceBar(SAMREEN_HR_PERMISSIONS))).toContain("Reports");
    expect(pagesIn(workspaceBar(EMPLOYEE_PERMISSIONS))).not.toContain("Reports");
  });
});
