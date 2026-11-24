// @vitest-environment jsdom
// The payroll reports branch filter is fed by the branch list. Someone who may not list branches (HR without branches.view)
// used to ask anyway and get a 403 (a red console error). Now the list is only requested when the viewer may read it.
import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API } from "@/lib/api/endpoints";

const permissions = vi.hoisted(() => ({ granted: new Set<string>() }));
const requested = vi.hoisted(() => ({ urls: [] as Array<string | null> }));

vi.mock("@/hooks/usePermission", () => ({ usePermission: (code: string) => permissions.granted.has(code) }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    requested.urls.push(url);
    return { data: null, loading: false, error: null, status: null, refetch: () => undefined };
  },
}));
vi.mock("@/lib/clientApi", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

import PayrollReports from "./PayrollReports";

beforeEach(() => { permissions.granted = new Set(); requested.urls = []; });
afterEach(() => cleanup());

describe("PayrollReports: the branch list", () => {
  it("is not requested when the viewer may not list branches", () => {
    render(<PayrollReports />);
    expect(requested.urls).not.toContain(API.branches.list);
    expect(requested.urls).toContain(API.payroll.cycles);
  });

  it("is requested when the viewer holds branches.view", () => {
    permissions.granted = new Set(["branches.view"]);
    render(<PayrollReports />);
    expect(requested.urls).toContain(API.branches.list);
  });
});
