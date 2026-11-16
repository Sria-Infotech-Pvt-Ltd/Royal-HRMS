// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, renderHook } from "@testing-library/react";
import type { TimesheetTeamPage } from "@/types/timesheet";

const urls: (string | null)[] = [];
let data: TimesheetTeamPage | null = null;
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => { urls.push(url); return { data: url ? data : null, loading: false, error: null, status: null, refetch: vi.fn() }; },
}));

import { queueUrl, useTimesheetPending, useTimesheetQueue } from "./useTimesheetQueue";

afterEach(() => { cleanup(); urls.length = 0; data = null; });

describe("queueUrl", () => {
  it("asks for one status, a page and the page size", () => {
    expect(queueUrl("submitted", 1)).toBe("/attendance/timesheets/team/?status=submitted&page=1&page_size=20");
    expect(queueUrl("returned", 3)).toBe("/attendance/timesheets/team/?status=returned&page=3&page_size=20");
  });
  it("leaves the status out for 'all'", () => {
    expect(queueUrl("all", 2)).toBe("/attendance/timesheets/team/?page=2&page_size=20");
  });
});

describe("useTimesheetQueue", () => {
  it("requests the filtered page and returns what the server sent", () => {
    data = { count: 1, page: 1, page_size: 20, total_pages: 1, results: [], pending_count: 4 };
    const { result } = renderHook(() => useTimesheetQueue("approved", 2));
    expect(urls[0]).toBe("/attendance/timesheets/team/?status=approved&page=2&page_size=20");
    expect(result.current.page?.pending_count).toBe(4);
  });
});

describe("useTimesheetPending", () => {
  it("asks for one row of the submitted list and reads the waiting count", () => {
    data = { count: 9, page: 1, page_size: 1, total_pages: 9, results: [], pending_count: 9 };
    const { result } = renderHook(() => useTimesheetPending(true));
    expect(urls[0]).toBe("/attendance/timesheets/team/?status=submitted&page_size=1");
    expect(result.current).toBe(9);
  });
  it("asks for nothing when the person has no timesheet tab", () => {
    const { result } = renderHook(() => useTimesheetPending(false));
    expect(urls[0]).toBeNull();
    expect(result.current).toBeNull();
  });
  it("is null until the answer arrives", () => {
    const { result } = renderHook(() => useTimesheetPending(true));
    expect(result.current).toBeNull();
  });
});
