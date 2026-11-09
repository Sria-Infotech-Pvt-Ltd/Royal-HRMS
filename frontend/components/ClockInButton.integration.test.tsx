// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";

// Integration test: the REAL ClockInButton + useClockWidget + useFaceVerificationStatus + punchGate + lockout lib,
// with only the network (useFetch / clientApi), toasts and the heavy camera modal replaced. The server answers are
// the exact flags the backend matrix test (apps.attendance.tests_face_mode_matrix) proves for each state.
type Guidance = {
  is_mandatory: boolean; registration_mode: string; state: string; can_self_register: boolean;
  requires_face_to_punch: boolean; message: string; fallback_active: boolean;
};
let guidance: Guidance;
const showToast = vi.fn();
const post = vi.fn();
const getCurrentPosition = vi.fn();

// Results must be referentially stable across renders (like the real hook's state), or the hook's effects loop.
const refetch = vi.fn();
const todayData = { is_clocked_in: false, session_seconds: 0, total_seconds: 0, punches: [] };
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string) => {
    if (url === API.attendance.faceVerification.status) return { data: guidance, loading: false, refetch };
    if (url === API.attendance.today) return { data: todayData, loading: false, refetch };
    return { data: null, loading: false, refetch };
  },
}));
vi.mock("@/lib/clientApi", () => ({ default: { post: (...a: unknown[]) => post(...a) } }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/app/dashboard/my-attendance/_components/CorrectionModal", () => ({ default: () => null }));
// Stand-in for the camera modal: renders a marker only while open, so "the camera opened" is observable.
vi.mock("@/components/FaceVerificationModal", () => ({
  default: ({ isOpen }: { isOpen: boolean }) => (isOpen ? <div data-testid="camera-open" /> : null),
}));

import ClockInButton from "./ClockInButton";

const base: Guidance = {
  is_mandatory: true, registration_mode: "self_service_hr_approval", state: "not_registered", can_self_register: true,
  requires_face_to_punch: false, message: "Please register your Face ID first.", fallback_active: false,
};

async function clickPunch(name: RegExp) {
  await act(async () => { fireEvent.click(screen.getByRole("button", { name })); });
}

beforeEach(() => {
  vi.useFakeTimers();
  window.sessionStorage.clear();
  showToast.mockReset(); post.mockReset(); getCurrentPosition.mockReset();
  getCurrentPosition.mockImplementation((ok: PositionCallback) =>
    ok({ coords: { latitude: 1, longitude: 2, accuracy: 3 } } as GeolocationPosition));
  Object.defineProperty(globalThis.navigator, "geolocation", { value: { getCurrentPosition }, configurable: true });
  guidance = { ...base };
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe.each(["default", "ess"] as const)("lockout integration (%s variant)", (variant) => {
  const name = /punch in/i;

  it("a 403 with data.blocked + retry_after_seconds disables the button, shows 'Please wait mm:ss', then re-enables", async () => {
    // Fallback allows a camera-less office punch, so the punch request is sent straight to the server.
    guidance = { ...base, fallback_active: true };
    post.mockImplementation((url: string) =>
      url === API.attendance.punch
        ? Promise.reject({ message: "Too many failed attempts.", data: { blocked: true, retry_after_seconds: 90 } })
        : Promise.resolve({}));
    render(<ClockInButton variant={variant} />);
    expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(false);

    await clickPunch(name);

    const locked = screen.getByRole("button", { name: /please wait 01:30/i }) as HTMLButtonElement;
    expect(locked.disabled).toBe(true);
    expect(locked.textContent?.trim()).toBe("Please wait 01:30"); // exact format, no extra text

    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(screen.getByRole("button", { name: /please wait 01:29/i })).toBeTruthy();

    await act(async () => { vi.advanceTimersByTime(89_000); });
    const reopened = screen.getByRole("button", { name }) as HTMLButtonElement;
    expect(reopened.disabled).toBe(false);
    expect(window.sessionStorage.getItem("aira_face_lockout_until")).toBeNull();
  });

  it("a 403 WITHOUT blocked=true does not start a countdown", async () => {
    guidance = { ...base, fallback_active: true };
    post.mockImplementation((url: string) =>
      url === API.attendance.punch ? Promise.reject({ message: "Outside geofence.", data: { retry_after_seconds: 90 } }) : Promise.resolve({}));
    render(<ClockInButton variant={variant} />);
    await clickPunch(name);
    expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByText(/please wait \d\d:\d\d/i)).toBeNull();
  });

  it("restores a still-running countdown after the page remounts (sessionStorage)", async () => {
    window.sessionStorage.setItem("aira_face_lockout_until", String(Date.now() + 65_000));
    await act(async () => { render(<ClockInButton variant={variant} />); }); // flush the mount effect
    expect(screen.getByRole("button", { name: /please wait 01:05/i })).toBeTruthy();
  });
});

describe("camera / punch gate by Face ID state (server flags -> real client behaviour)", () => {
  const cases: Array<[string, Partial<Guidance>, { camera: boolean; punchPosted: boolean; toast: boolean }]> = [
    ["approved", { state: "approved", requires_face_to_punch: true }, { camera: true, punchPosted: false, toast: false }],
    ["not_registered", { state: "not_registered" }, { camera: false, punchPosted: false, toast: true }],
    ["pending", { state: "pending", can_self_register: false }, { camera: false, punchPosted: false, toast: true }],
    ["rejected", { state: "rejected" }, { camera: false, punchPosted: false, toast: true }],
    ["not_registered + fallback active", { fallback_active: true }, { camera: false, punchPosted: true, toast: false }],
    ["pending + fallback active", { state: "pending", can_self_register: false, fallback_active: true }, { camera: false, punchPosted: true, toast: false }],
    ["Face ID off", { is_mandatory: false }, { camera: false, punchPosted: true, toast: false }],
  ];

  it.each(cases)("%s", async (_label, patch, expected) => {
    guidance = { ...base, ...patch };
    post.mockResolvedValue({ data: { message: "ok", data: null } });
    render(<ClockInButton />);
    await clickPunch(/punch in/i);

    expect(!!screen.queryByTestId("camera-open")).toBe(expected.camera);
    expect(post.mock.calls.some((c) => c[0] === API.attendance.punch)).toBe(expected.punchPosted);
    expect(showToast.mock.calls.some((c) => c[1] === "error")).toBe(expected.toast);
    if (expected.toast) {
      expect(showToast).toHaveBeenCalledWith(base.message, "error");
      // stopped before GPS and the camera
      expect(getCurrentPosition).not.toHaveBeenCalled();
    }
  });
});
