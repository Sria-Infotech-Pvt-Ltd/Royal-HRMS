// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API } from "@/lib/api/endpoints";
import { useClockWidget } from "./useClockWidget";

const post = vi.fn();
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast: vi.fn() }) }));
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: null, loading: false, refetch: vi.fn() }) }));
vi.mock("@/hooks/useFaceVerificationStatus", () => ({
  useFaceVerificationStatus: () => ({ data: null, loading: false, refetch: vi.fn() }),
}));
vi.mock("@/lib/faceApi/punchGate", () => ({
  faceGateFor: () => ({ required: false, registrationMissing: false, fallbackActive: false, message: "" }),
}));

const position = { coords: { latitude: 17.385, longitude: 78.486, accuracy: 12 } };

beforeEach(() => {
  post.mockReset().mockResolvedValue({ data: {} });
  Object.defineProperty(globalThis.navigator, "geolocation", {
    configurable: true,
    value: { getCurrentPosition: vi.fn((resolve: (value: unknown) => void) => resolve(position)) },
  });
});
afterEach(() => cleanup());

describe("useClockWidget.prepareLocation", () => {
  it("captures the location and runs the geofence check for a WFH punch, which the server needs to validate it", async () => {
    const { result } = renderHook(() => useClockWidget());
    let outcome: Awaited<ReturnType<typeof result.current.prepareLocation>> | undefined;
    await act(async () => { outcome = await result.current.prepareLocation("wfh"); });
    expect(outcome).toEqual({ ok: true, location: { latitude: 17.385, longitude: 78.486, accuracy: 12 } });
    expect(post).toHaveBeenCalledWith(API.attendance.geofenceCheck, { attendance_mode: "wfh", latitude: 17.385, longitude: 78.486, accuracy: 12 });
  });

  it("still does the same for an office punch", async () => {
    const { result } = renderHook(() => useClockWidget());
    let outcome: Awaited<ReturnType<typeof result.current.prepareLocation>> | undefined;
    await act(async () => { outcome = await result.current.prepareLocation("office"); });
    expect(outcome?.location).not.toBeNull();
    expect(post).toHaveBeenCalledWith(API.attendance.geofenceCheck, expect.objectContaining({ attendance_mode: "office" }));
  });

  it("passes modes without a geofence straight through with no location", async () => {
    const { result } = renderHook(() => useClockWidget());
    let outcome: Awaited<ReturnType<typeof result.current.prepareLocation>> | undefined;
    await act(async () => { outcome = await result.current.prepareLocation("field"); });
    expect(outcome).toEqual({ ok: true, location: null });
    expect(post).not.toHaveBeenCalled();
  });
});
