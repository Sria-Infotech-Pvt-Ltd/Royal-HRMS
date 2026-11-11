import { describe, expect, it } from "vitest";
import { KIND_MODULES, hasModule, moduleForPath, modulesFromPayload } from "./modules";
import { buildNav, isSection, type NavItem } from "./navConfig";

describe("modules", () => {
  it("unknown module list shows everything", () => {
    expect(hasModule(undefined, "payroll")).toBe(true);
    expect(hasModule(["leave"], "payroll")).toBe(false);
    expect(hasModule(["leave"], undefined)).toBe(true);
  });

  it("maps routes to modules, longest prefix first", () => {
    expect(moduleForPath("/dashboard/payroll/runs/1")).toBe("payroll");
    expect(moduleForPath("/dashboard/settings/payroll-config")).toBe("payroll");
    expect(moduleForPath("/dashboard/settings/company")).toBeUndefined();
    expect(moduleForPath("/dashboard/employees")).toBeUndefined();
  });

  it("reads the claim safely", () => {
    expect(modulesFromPayload({ modules: ["leave"] })).toEqual(["leave"]);
    expect(modulesFromPayload({})).toBeUndefined();
    expect(modulesFromPayload({ modules: [1] })).toBeUndefined();
  });
});

describe("buildNav with modules", () => {
  const ids = (entries: ReturnType<typeof buildNav>) =>
    entries.filter(e => !isSection(e)).map(e => (e as NavItem).id);
  const perms = ["payroll.view", "leave.view", "employees.view", "expenses.view"];

  it("without a module list, behaves as before", () => {
    expect(ids(buildNav(perms))).toEqual(expect.arrayContaining(["payroll", "leave", "employees"]));
  });

  it("hides items of modules the company doesn't have; core stays", () => {
    const visible = ids(buildNav(perms, ["leave"]));
    expect(visible).toContain("leave");
    expect(visible).toContain("employees");
    expect(visible).not.toContain("payroll");
    expect(visible).not.toContain("my-payslip");
    expect(visible).not.toContain("expenses");
  });
});

describe("subscription coverage", () => {
  it("maps every module page, incl. candidate review, to its module", () => {
    expect(moduleForPath("/dashboard/candidate-review")).toBe("recruitment");
    expect(moduleForPath("/dashboard/settings/payroll-config")).toBe("payroll");
    expect(moduleForPath("/dashboard/settings/assets")).toBe("assets");
    expect(moduleForPath("/dashboard/employees")).toBeUndefined();          // core
  });

  it("maps request / approval kinds to modules", () => {
    expect(KIND_MODULES).toMatchObject({ leave: "leave", wfh: "wfh", expense: "expenses",
      attendance_correction: "attendance", payslip: "payroll", separation: "separation" });
  });

  it("a Starter company sees no payroll, recruitment, expense or asset menus", () => {
    const starter = ["announcements", "attendance", "documents", "leave", "wfh"];
    // An HR user: the HR Attendance menu needs attendance.edit (lib/navConfig.ts).
    const all = ["recruitment.view", "payroll.view", "leave.view", "expenses.view", "attendance.edit",
      "employees.view", "documents.view", "wfh.view", "settings.view"];
    const visible = buildNav(all, starter).filter(e => !isSection(e)).map(e => (e as NavItem).id);
    for (const hidden of ["payroll", "my-payslip", "expenses", "interview-list", "candidate-review", "email-logs", "referrals"]) {
      expect(visible).not.toContain(hidden);
    }
    for (const shown of ["leave", "attendance", "documents", "work-from-home", "employees", "settings"]) {
      expect(visible).toContain(shown);
    }
  });
});
