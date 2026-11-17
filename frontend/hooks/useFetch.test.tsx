// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useFetch } from "./useFetch";

const get = vi.fn();
vi.mock("@/lib/clientApi", () => ({ default: { get: (...args: unknown[]) => get(...args) } }));

interface Pending { resolve: (value: unknown) => void; reject: (reason: unknown) => void }
let pending: Pending[] = [];

function respond(index: number, data: unknown) {
  pending[index].resolve({ data: { data } });
}

beforeEach(() => {
  pending = [];
  get.mockReset().mockImplementation(() => new Promise((resolve, reject) => { pending.push({ resolve, reject }); }));
});
afterEach(() => cleanup());

describe("useFetch: identical requests in flight are shared", () => {
  it("makes one request for the same URL asked for at the same moment, and gives every caller the answer", async () => {
    const first = renderHook(() => useFetch<string>("/attendance/today/"));
    const second = renderHook(() => useFetch<string>("/attendance/today/"));
    const third = renderHook(() => useFetch<string>("/attendance/today/"));
    expect(get).toHaveBeenCalledTimes(1);
    await act(async () => { respond(0, "figures"); });
    await waitFor(() => expect(third.result.current.data).toBe("figures"));
    expect(first.result.current.data).toBe("figures");
    expect(second.result.current.data).toBe("figures");
  });

  it("keeps different URLs, and the signed-in-user variant of a URL, apart", () => {
    renderHook(() => useFetch<string>("/a/"));
    renderHook(() => useFetch<string>("/b/"));
    renderHook(() => useFetch<string>("/a/", { asSignedInUser: true }));
    expect(get).toHaveBeenCalledTimes(3);
  });

  it("asks again once the first request has finished, so nothing stale is served", async () => {
    const first = renderHook(() => useFetch<string>("/attendance/today/"));
    await act(async () => { respond(0, "morning"); });
    await waitFor(() => expect(first.result.current.data).toBe("morning"));
    const later = renderHook(() => useFetch<string>("/attendance/today/"));
    expect(get).toHaveBeenCalledTimes(2);
    await act(async () => { respond(1, "afternoon"); });
    await waitFor(() => expect(later.result.current.data).toBe("afternoon"));
  });

  it("makes its own request on refetch, even while another is in flight, so it cannot get an answer from before the change", async () => {
    const view = renderHook(() => useFetch<string>("/attendance/today/"));
    expect(get).toHaveBeenCalledTimes(1);
    act(() => { view.result.current.refetch(); });
    expect(get).toHaveBeenCalledTimes(2);
    await act(async () => { respond(1, "after the punch"); });
    await waitFor(() => expect(view.result.current.data).toBe("after the punch"));
  });

  it("gives every caller the failure when the shared request fails, and allows a retry afterwards", async () => {
    const first = renderHook(() => useFetch<string>("/attendance/today/"));
    const second = renderHook(() => useFetch<string>("/attendance/today/"));
    await act(async () => { pending[0].reject({ response: { data: { message: "Server error" } }, status: 500 }); });
    await waitFor(() => expect(second.result.current.error).toBe("Server error"));
    expect(first.result.current.error).toBe("Server error");
    renderHook(() => useFetch<string>("/attendance/today/"));
    expect(get).toHaveBeenCalledTimes(2);
  });
});
