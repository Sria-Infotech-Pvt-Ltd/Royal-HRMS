import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

// Each workflow list is requested only when the person may approve it; the corrections list needs attendance.view.
let allowed: Set<string>;
let requested: string[];

vi.mock("@/hooks/usePermission", () => ({ usePermission: (code: string) => allowed.has(code) }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    if (url) requested.push(url);
    return { data: null, loading: false, error: null, status: null, refetch: () => {} };
  },
}));

import { useApprovalOverview } from "./useApprovalOverview";

function Probe({ includeTeam }: { includeTeam: boolean }) {
  const overview = useApprovalOverview({ includeTeam, includeFace: false });
  return <span>{overview.team.map(count => count.kind).join(",")}</span>;
}
const run = (includeTeam = true) => renderToStaticMarkup(<Probe includeTeam={includeTeam} />);
const corrections = () => requested.some(url => url.startsWith("/attendance/corrections/"));

beforeEach(() => {
  requested = [];
  allowed = new Set();
});

describe("useApprovalOverview corrections gate", () => {
  it("does not request attendance corrections without attendance.view", () => {
    allowed = new Set(["leave.approve"]);
    run();
    expect(corrections()).toBe(false);
  });

  it("attendance.create alone no longer opens the corrections request", () => {
    allowed = new Set(["attendance.create"]);
    run();
    expect(corrections()).toBe(false);
  });

  it("requests attendance corrections with attendance.view", () => {
    allowed = new Set(["attendance.view"]);
    expect(run()).toContain("attendance_correction");
    expect(corrections()).toBe(true);
  });

  it("requests nothing at all when the team section is switched off", () => {
    allowed = new Set(["attendance.view", "leave.approve", "wfh.approve", "expenses.approve", "separation.approve"]);
    run(false);
    expect(requested).toEqual([]);
  });

  it("only lists the workflows the person may approve", () => {
    allowed = new Set(["leave.approve"]);
    expect(run()).toBe("<span>leave</span>");
  });
});
