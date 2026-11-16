// @vitest-environment jsdom
import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coversToday, useTodayAttendanceMode } from "./useTodayAttendanceMode";

let fetched: { results: { start_date: string; end_date: string }[] } | null = null;
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: fetched, loading: false, refetch: vi.fn() }) }));

afterEach(() => { cleanup(); fetched = null; });

const today = new Date();
const iso = (offsetDays: number) => {
  const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() + offsetDays);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
};

describe("coversToday", () => {
  it("includes both ends of the range and excludes other days", () => {
    expect(coversToday({ start_date: iso(0), end_date: iso(0) })).toBe(true);
    expect(coversToday({ start_date: iso(-2), end_date: iso(1) })).toBe(true);
    expect(coversToday({ start_date: iso(1), end_date: iso(3) })).toBe(false);
    expect(coversToday({ start_date: iso(-3), end_date: iso(-1) })).toBe(false);
  });
});

describe("useTodayAttendanceMode", () => {
  it("is wfh when an approved request covers today", () => {
    fetched = { results: [{ start_date: iso(0), end_date: iso(0) }] };
    expect(renderHook(() => useTodayAttendanceMode()).result.current).toBe("wfh");
  });
  it("is office with no request, or only requests for other days, or before the list has loaded", () => {
    fetched = { results: [{ start_date: iso(2), end_date: iso(3) }] };
    expect(renderHook(() => useTodayAttendanceMode()).result.current).toBe("office");
    fetched = { results: [] };
    expect(renderHook(() => useTodayAttendanceMode()).result.current).toBe("office");
    fetched = null;
    expect(renderHook(() => useTodayAttendanceMode()).result.current).toBe("office");
  });
});
