import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

// The Workforce dashboard's lower section keeps the lifecycle register and the safeguards strip only. The per-module
// shortcut tiles (and the request each one made) were removed, and the system-health request still needs settings.edit.
let allowed: Set<string>;
let requested: string[];

vi.mock("@/hooks/usePermission", () => ({ usePermission: (code: string) => allowed.has(code) }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    if (url) requested.push(url);
    return { data: null, loading: false, error: null, status: null, refetch: () => {} };
  },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));

import WorkforceOperations from "./WorkforceOperations";

const REMOVED_MODULE_REQUESTS = [
  "/dashboard/module/attendance-overview/",
  "/dashboard/module/payroll-overview/",
  "/dashboard/module/performance-overview/",
  "/dashboard/module/leave-overview/",
  "/dashboard/module/settings-overview/",
  "/dashboard/hr/recruitment-funnel/",
];
const HEALTH = "/dashboard/system-admin/kpis/";
const render = () => renderToStaticMarkup(<WorkforceOperations overview={null} overviewLoading={false} />);
const wasRequested = (path: string) => requested.some(url => url.startsWith(path));

beforeEach(() => {
  requested = [];
  allowed = new Set();
});

describe("WorkforceOperations requests", () => {
  it("no longer requests the per-module overviews, whatever the permissions", () => {
    allowed = new Set(["attendance.view", "payroll.view", "performance.manage_cycles", "settings.edit"]);
    render();
    for (const path of REMOVED_MODULE_REQUESTS) expect(wasRequested(path), path).toBe(false);
  });

  it("requests system health only with settings.edit", () => {
    render();
    expect(wasRequested(HEALTH)).toBe(false);
    requested = [];
    allowed = new Set(["settings.edit"]);
    render();
    expect(wasRequested(HEALTH)).toBe(true);
  });

  it("still requests the lifecycle register for everyone", () => {
    render();
    expect(wasRequested("/dashboard/hr/lifecycle-register/")).toBe(true);
  });
});

describe("WorkforceOperations sections", () => {
  it("keeps the lifecycle register and the safeguards strip", () => {
    const html = render();
    expect(html).toContain("Lifecycle action register");
    expect(html).toContain("Platform safeguards");
  });

  it("drops the banner, the module tiles and the tool tiles", () => {
    const html = render();
    for (const gone of ["Artificial Intelligence Resources Assistance", "Complete capability coverage", "Operational tools"]) {
      expect(html).not.toContain(gone);
    }
  });
});
