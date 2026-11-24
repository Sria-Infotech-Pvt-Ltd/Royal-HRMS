import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { ALL_NAV, isSection } from "@/lib/navConfig";

// The route guard (proxy.ts) decides who may OPEN a page; the menu (navConfig.ts) decides who SEES its link. When a menu entry
// asks for a permission but the guard has no rule for that page, anyone signed in can open it by typing the address, and
// the page's own requests are then refused. This keeps the two in step.
const proxySource = readFileSync(path.join(process.cwd(), "proxy.ts"), "utf8");
const guardedRoutes = [...proxySource.matchAll(/^\s*"(\/[^"]+)"\s*:/gm)].map(match => match[1]);

// Pages that are deliberately self-service: every employee may open them and the page itself shows what that person may see.
const OPEN_ON_PURPOSE = new Set([
  "/dashboard/assessments",     // each employee's own assessments (proxy.ts explains it)
  "/dashboard/work-from-home",  // every employee can request work from home (wfh.view is a baseline permission)
]);

describe("route guard vs menu", () => {
  const gatedItems = ALL_NAV.filter((entry): entry is Exclude<typeof entry, { section: string }> => !isSection(entry))
    .filter(item => item.permission !== null && item.permission !== undefined);

  it("guards every page whose menu entry needs a permission, except the deliberate self-service ones", () => {
    const unguarded = gatedItems
      .map(item => item.path)
      .filter(route => !OPEN_ON_PURPOSE.has(route) && !guardedRoutes.some(guarded => route === guarded || route.startsWith(`${guarded}/`)));
    expect(unguarded).toEqual([]);
  });

  it("guards the Face ID registrations page with the permission its menu entry and API need", () => {
    expect(proxySource).toMatch(/"\/dashboard\/face-id-registrations"\s*:\s*"facial_recognition\.approve"/);
  });

  it("lets the Branches page be opened with branches.view, which is what its menu and list API use", () => {
    expect(proxySource).toMatch(/"\/dashboard\/branches"\s*:\s*\[\s*"branches\.view"/);
  });
});
