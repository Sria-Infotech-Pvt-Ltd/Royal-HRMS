// @vitest-environment jsdom
import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = { pathname: "/dashboard/ess", query: "", fetched: [] as (string | null)[], data: null as unknown };
vi.mock("next/navigation", () => ({ usePathname: () => state.pathname, useSearchParams: () => new URLSearchParams(state.query) }));
vi.mock("@/hooks/useFetch", () => ({ useFetch: (url: string | null) => { state.fetched.push(url); return { data: url ? state.data : null }; } }));

import { useViewedAccess } from "./useViewedAccess";

const ACCESS = { permissions: ["leave.view"], can_manage_team: false, can_manage_branch: false, is_superuser: false };

beforeEach(() => { state.pathname = "/dashboard/ess"; state.query = ""; state.fetched = []; state.data = ACCESS; });

describe("useViewedAccess", () => {
  it("asks for the employee's own access while their workspace is being viewed", () => {
    state.query = "as=EMP00081";
    const { result } = renderHook(() => useViewedAccess());
    expect(result.current.isViewing).toBe(true);
    expect(result.current.access).toEqual(ACCESS);
    expect(state.fetched).toEqual(["/employees/me/access/?as=EMP00081"]);
  });

  it("asks for nothing on a normal page, a normal workspace, or a made-up address", () => {
    for (const [pathname, query] of [["/dashboard/ess", ""], ["/dashboard/employees", "as=EMP00081"], ["/dashboard/ess", "as=../x"]]) {
      state.pathname = pathname; state.query = query; state.fetched = [];
      const { result } = renderHook(() => useViewedAccess());
      expect(result.current.isViewing).toBe(false);
      expect(result.current.access).toBeNull();
      expect(state.fetched.every(url => url === null)).toBe(true);
    }
  });

  it("offers nothing until the employee's access has loaded", () => {
    state.query = "as=EMP00081"; state.data = null;
    const { result } = renderHook(() => useViewedAccess());
    expect(result.current.isViewing).toBe(true);
    expect(result.current.access).toBeNull();
  });
});
