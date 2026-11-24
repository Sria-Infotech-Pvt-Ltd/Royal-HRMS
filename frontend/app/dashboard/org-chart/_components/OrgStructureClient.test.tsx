// @vitest-environment jsdom
// The org chart feeds its edit pop-ups and branch filter from the employee and branch lists. A viewer who may not read those
// lists (an ordinary employee) used to ask anyway and get two 403s, which show as red console errors. Now they are not asked for.
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API } from "@/lib/api/endpoints";

const permissions = vi.hoisted(() => ({ granted: new Set<string>() }));
const requested = vi.hoisted(() => ({ urls: [] as Array<string | null> }));
const get = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/usePermission", () => ({
  usePermission: (code: string) => permissions.granted.has(code),
  useAnyPermission: (...codes: string[]) => codes.some(code => permissions.granted.has(code)),
}));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    requested.urls.push(url);
    return { data: null, loading: false, error: null, status: null, refetch: () => undefined };
  },
}));
vi.mock("@/lib/clientApi", () => ({ default: { get, post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));
vi.mock("@/components/SearchableSelect", () => ({ default: () => null }));
vi.mock("./OrgTree", () => ({ default: () => null }));
vi.mock("./OrgDetail", () => ({ default: () => null }));
vi.mock("./OrgChartView", () => ({ default: () => null }));
vi.mock("./OrgOverview", () => ({ default: () => null }));
vi.mock("./OrgReportingChart", () => ({ default: () => null }));
vi.mock("./AddUnitModal", () => ({ default: () => null }));
vi.mock("./AddPositionModal", () => ({ default: () => null }));
vi.mock("./AssignHolderModal", () => ({ default: () => null }));
vi.mock("./EndPlacementModal", () => ({ default: () => null }));
vi.mock("./DeactivatePositionModal", () => ({ default: () => null }));
vi.mock("./PositionPermissionsModal", () => ({ default: () => null }));
vi.mock("./ManageJobTemplatesModal", () => ({ default: () => null }));

import OrgStructureClient from "./OrgStructureClient";

beforeEach(() => {
  permissions.granted = new Set();
  requested.urls = [];
  get.mockReset();
  get.mockResolvedValue({ data: { data: { results: [] } } });
});
afterEach(() => cleanup());

describe("OrgStructureClient: the employee and branch lists", () => {
  it("does not ask for them when the viewer may not read them", async () => {
    render(<OrgStructureClient />);
    await waitFor(() => expect(get).toHaveBeenCalled());
    const asked = requested.urls.filter((url): url is string => Boolean(url));
    expect(asked.some(url => url.startsWith(API.employees.list))).toBe(false);
    expect(asked.some(url => url.startsWith(API.branches.list))).toBe(false);
    expect(get.mock.calls.some(([url]) => String(url).startsWith(API.employees.list) || String(url).startsWith(API.branches.list))).toBe(false);
  });

  it("asks for them when the viewer holds the permissions", async () => {
    permissions.granted = new Set(["employees.view", "branches.view"]);
    render(<OrgStructureClient />);
    await waitFor(() => expect(get).toHaveBeenCalled());
    expect(requested.urls).toContain(`${API.employees.list}?page_size=200&status=active`);
    expect(requested.urls).toContain(`${API.branches.list}?page_size=200`);
  });
});
