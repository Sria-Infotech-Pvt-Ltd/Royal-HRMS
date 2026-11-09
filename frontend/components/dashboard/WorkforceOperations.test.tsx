import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

// Each module overview on the Workforce dashboard must be requested only by someone whose permission the API requires;
// the other requests (leave, recruitment, ...) are untouched.
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

const OVERVIEWS = {
  attendance: "/dashboard/module/attendance-overview/",
  payroll: "/dashboard/module/payroll-overview/",
  performance: "/dashboard/module/performance-overview/",
  kpis: "/dashboard/system-admin/kpis/",
};
const render = () => renderToStaticMarkup(<WorkforceOperations overview={null} overviewLoading={false} />);
const wasRequested = (path: string) => requested.some(url => url.startsWith(path));

beforeEach(() => {
  requested = [];
  allowed = new Set();
});

describe("WorkforceOperations requests", () => {
  it("requests none of the four gated overviews without their permissions", () => {
    render();
    for (const path of Object.values(OVERVIEWS)) expect(wasRequested(path), path).toBe(false);
  });

  it("requests each overview only with its own permission", () => {
    const cases: [string, string][] = [
      ["attendance.view", OVERVIEWS.attendance], ["payroll.view", OVERVIEWS.payroll],
      ["performance.manage_cycles", OVERVIEWS.performance], ["settings.edit", OVERVIEWS.kpis],
    ];
    for (const [permission, path] of cases) {
      requested = [];
      allowed = new Set([permission]);
      render();
      expect(wasRequested(path), `${permission} -> ${path}`).toBe(true);
      const others = Object.values(OVERVIEWS).filter(other => other !== path);
      for (const other of others) expect(wasRequested(other), `${permission} must not request ${other}`).toBe(false);
    }
  });

  it("still requests the ungated sources (leave overview) for everyone", () => {
    render();
    expect(wasRequested("/dashboard/module/leave-overview/")).toBe(true);
  });

  it("hides the cards for modules the person cannot see", () => {
    const html = render();
    for (const label of ["Attendance", "Payroll", "Performance"]) expect(html).not.toContain(`>${label}<`);
  });
});
