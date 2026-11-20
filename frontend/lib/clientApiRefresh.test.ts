// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";

// The REAL clientApi interceptor and refresh coordination. Replaced: the HTTP adapter of clientApi (the API server), the
// refresh POST (plain axios.post), and clearAuth.
const mocks = vi.hoisted(() => ({ post: vi.fn(), clearAuth: vi.fn() }));
vi.mock("./auth", () => ({ clearAuth: () => mocks.clearAuth() }));
vi.mock("axios", async importOriginal => {
  const actual = await importOriginal<typeof import("axios")>();
  actual.default.post = ((...args: unknown[]) => mocks.post(...args)) as typeof actual.default.post;
  return actual;
});

import clientApi, {
  isRefreshTokenRejected, isSessionKnownExpired, loginNeedsRenewal, refreshAccessToken, refreshAccessTokenQuietly, renewLoginIfStale, resetSessionExpired,
} from "./clientApi";

const LAST_REFRESH_KEY = "royal_hrms_last_token_refresh_at";   // the key the other tab writes after it refreshed

// ── a fake API server: requests succeed only while the access token is valid ─────────────────────────────────────────
let accessValid = false;
let apiCalls: string[] = [];

function reply(config: InternalAxiosRequestConfig, status: number, data: unknown): AxiosResponse {
  return { data, status, statusText: String(status), headers: {}, config };
}

async function adapter(config: InternalAxiosRequestConfig): Promise<AxiosResponse> {
  apiCalls.push(config.url ?? "");
  if (accessValid) return reply(config, 200, { ok: true });
  throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, reply(config, 401, { message: "Unauthorized" }));
}

// ── ways the refresh call itself can fail ────────────────────────────────────────────────────────────────────────────
function httpFailure(status: number, message = "Server said no."): AxiosError {
  const response = reply({} as InternalAxiosRequestConfig, status, { status: "error", message, data: {} });
  return new AxiosError(`Request failed with status code ${status}`, "ERR_BAD_RESPONSE", undefined, null, response);
}
const networkFailure = () => new AxiosError("Network Error", "ERR_NETWORK");
const timeoutFailure = () => new AxiosError("timeout of 15000ms exceeded", "ECONNABORTED");

function refreshWillSucceed() {
  mocks.post.mockImplementation(async () => { accessValid = true; return { status: 200, data: {} }; });
}

let expiredEvents = 0;
const onExpired = () => { expiredEvents += 1; };

beforeEach(() => {
  accessValid = false;
  apiCalls = [];
  expiredEvents = 0;
  mocks.post.mockReset();
  mocks.clearAuth.mockReset();
  localStorage.clear();
  resetSessionExpired();
  clientApi.defaults.adapter = adapter;
  window.addEventListener("session:expired", onExpired);
});
afterEach(() => {
  window.removeEventListener("session:expired", onExpired);
  Reflect.deleteProperty(navigator, "locks");
});

describe("a refresh that fails for a reason other than the token being rejected keeps the session", () => {
  it.each([
    ["503 (the database is briefly unavailable)", () => httpFailure(503, "Database is temporarily unavailable. Please try again in a moment.")],
    ["500", () => httpFailure(500)],
    ["502", () => httpFailure(502)],
    ["504", () => httpFailure(504)],
    ["403", () => httpFailure(403)],
    ["a timeout", timeoutFailure],
    ["a dropped connection / no network", networkFailure],
  ])("%s: the request fails, the person stays signed in", async (_label, failure) => {
    mocks.post.mockRejectedValue(failure());
    await expect(clientApi.get("/leave/requests/")).rejects.toBeTruthy();
    expect(expiredEvents).toBe(0);                    // no logout event, so no redirect to /login
    expect(isSessionKnownExpired()).toBe(false);
    expect(mocks.clearAuth).not.toHaveBeenCalled();   // the stored identity is untouched
  });

  it("shows the server's own reason for a 503 rather than a bare failure", async () => {
    mocks.post.mockRejectedValue(httpFailure(503, "Database is temporarily unavailable. Please try again in a moment."));
    await expect(clientApi.get("/leave/requests/")).rejects.toThrow("Database is temporarily unavailable");
  });

  it("recovers on the next request once the database is back: the session was never lost", async () => {
    mocks.post.mockRejectedValueOnce(httpFailure(503));
    await expect(clientApi.get("/leave/requests/")).rejects.toBeTruthy();

    refreshWillSucceed();                              // the database is back
    const response = await clientApi.get("/leave/requests/");
    expect(response.status).toBe(200);
    expect(mocks.post).toHaveBeenCalledTimes(2);       // it tried the refresh again instead of giving up for good
    expect(expiredEvents).toBe(0);
  });

  it("also fails the requests that were waiting on that refresh, without ending the session", async () => {
    mocks.post.mockRejectedValue(httpFailure(503));
    const results = await Promise.allSettled([clientApi.get("/a/"), clientApi.get("/b/"), clientApi.get("/c/")]);
    expect(results.map(result => result.status)).toEqual(["rejected", "rejected", "rejected"]);
    expect(mocks.post).toHaveBeenCalledTimes(1);
    expect(expiredEvents).toBe(0);
  });
});

describe("a refresh token the server rejects ends the session", () => {
  it("401: the session is expired, auth is cleared and the logout event fires once", async () => {
    mocks.post.mockRejectedValue(httpFailure(401, "Token is invalid or expired."));
    await expect(clientApi.get("/leave/requests/")).rejects.toBeTruthy();
    expect(expiredEvents).toBe(1);
    expect(isSessionKnownExpired()).toBe(true);
    expect(mocks.clearAuth).toHaveBeenCalledTimes(1);
  });

  it("then stops spending refresh calls on requests that are still in flight", async () => {
    mocks.post.mockRejectedValue(httpFailure(401));
    await expect(clientApi.get("/a/")).rejects.toBeTruthy();
    await expect(clientApi.get("/b/")).rejects.toBeTruthy();
    expect(mocks.post).toHaveBeenCalledTimes(1);
  });

  it("isRefreshTokenRejected is true only for a 401", () => {
    expect(isRefreshTokenRejected(httpFailure(401))).toBe(true);
    for (const status of [400, 403, 404, 429, 500, 502, 503, 504]) expect(isRefreshTokenRejected(httpFailure(status))).toBe(false);
    expect(isRefreshTokenRejected(networkFailure())).toBe(false);
    expect(isRefreshTokenRejected(timeoutFailure())).toBe(false);
    expect(isRefreshTokenRejected(new Error("boom"))).toBe(false);
    expect(isRefreshTokenRejected(undefined)).toBe(false);
  });
});

describe("refresh coordination", () => {
  it("a normal expiry refreshes once and retries the request", async () => {
    refreshWillSucceed();
    const response = await clientApi.get("/leave/requests/");
    expect(response.status).toBe(200);
    expect(mocks.post).toHaveBeenCalledTimes(1);
    expect(apiCalls).toEqual(["/leave/requests/", "/leave/requests/"]);   // the original, then the retry
    expect(localStorage.getItem(LAST_REFRESH_KEY)).not.toBeNull();         // so another tab can tell it just happened
  });

  it("sends the refresh with credentials and a timeout, so a hung refresh cannot hold the lock for ever", async () => {
    refreshWillSucceed();
    await clientApi.get("/leave/requests/");
    const options = mocks.post.mock.calls[0][2] as { withCredentials: boolean; timeout: number };
    expect(options.withCredentials).toBe(true);
    expect(options.timeout).toBe(15000);
  });

  it("many requests expiring together cause ONE refresh and all succeed afterwards", async () => {
    refreshWillSucceed();
    const responses = await Promise.all(Array.from({ length: 6 }, (_, index) => clientApi.get(`/page/${index}/`)));
    expect(responses.map(response => response.status)).toEqual([200, 200, 200, 200, 200, 200]);
    expect(mocks.post).toHaveBeenCalledTimes(1);
  });

  it("the quiet (notification) refresh and a request's own refresh share one call in the same tab", async () => {
    let finish: () => void = () => undefined;
    mocks.post.mockImplementation(() => new Promise(resolve => { finish = () => { accessValid = true; resolve({ status: 200 }); }; }));
    const quiet = refreshAccessTokenQuietly();
    const request = clientApi.get("/leave/requests/");
    // Let the request reach its 401 and ask for a refresh WHILE the quiet one is still in flight: that overlap is the case.
    await vi.waitFor(() => expect(apiCalls).toHaveLength(1));
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(mocks.post).toHaveBeenCalledTimes(1);      // two callers, one call to the server, while both are waiting
    finish();
    await Promise.all([quiet, request]);
    expect(mocks.post).toHaveBeenCalledTimes(1);      // not two calls racing with the same rotating refresh token
    expect(apiCalls).toEqual(["/leave/requests/", "/leave/requests/"]);   // and the request was retried after it
  });

  it("two direct callers in one tab also share one call, even where navigator.locks does not exist", async () => {
    refreshWillSucceed();
    await Promise.all([refreshAccessToken(), refreshAccessToken(), refreshAccessTokenQuietly()]);
    expect(mocks.post).toHaveBeenCalledTimes(1);
  });

  it("a later refresh, once the first has finished, goes ahead (the in-flight call is released)", async () => {
    refreshWillSucceed();
    await refreshAccessToken();
    localStorage.clear();                              // pretend the recent-refresh window has passed
    await refreshAccessToken();
    expect(mocks.post).toHaveBeenCalledTimes(2);
  });

  it("the quiet refresh never throws and never ends the session, even when the token is rejected", async () => {
    mocks.post.mockRejectedValue(httpFailure(401));
    await expect(refreshAccessTokenQuietly()).resolves.toBeUndefined();
    expect(expiredEvents).toBe(0);
    expect(isSessionKnownExpired()).toBe(false);      // the next real request's 401 is what ends the session, properly
    mocks.post.mockRejectedValue(httpFailure(503));
    await expect(refreshAccessTokenQuietly()).resolves.toBeUndefined();
  });
});

describe("cross-tab refresh", () => {
  it("skips its own refresh when another tab refreshed moments ago, and retries with the shared cookie", async () => {
    localStorage.setItem(LAST_REFRESH_KEY, String(Date.now()));   // the other tab just rotated the cookie
    let firstCall = true;
    clientApi.defaults.adapter = async config => {
      apiCalls.push(config.url ?? "");
      if (firstCall) {                                           // this tab's cookie was stale for the first attempt only
        firstCall = false;
        throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, reply(config, 401, {}));
      }
      return reply(config, 200, { ok: true });
    };
    const response = await clientApi.get("/leave/requests/");
    expect(response.status).toBe(200);
    expect(mocks.post).not.toHaveBeenCalled();                    // no second rotation of the same refresh token
  });

  it("two tabs expiring at the same moment make one call between them (the lock serializes, the second sees it was done)", async () => {
    // A lock shared by both "tabs", granted one holder at a time in arrival order, like navigator.locks.
    let tail: Promise<unknown> = Promise.resolve();
    const sharedLocks = {
      request: (_name: string, callback: () => Promise<void>) => {
        const run = tail.then(callback, callback);
        tail = run.catch(() => undefined);
        return run;
      },
    };
    Object.defineProperty(navigator, "locks", { value: sharedLocks, configurable: true });

    let finish: () => void = () => undefined;
    mocks.post.mockImplementation(() => new Promise(resolve => { finish = () => resolve({ status: 200 }); }));

    const tabA = await import("./clientApi");
    vi.resetModules();
    const tabB = await import("./clientApi");                    // a second copy of the module: its own state, as in a second tab
    expect(tabB.refreshAccessToken).not.toBe(tabA.refreshAccessToken);

    const refreshA = tabA.refreshAccessToken();
    const refreshB = tabB.refreshAccessToken();
    await vi.waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(1));   // only the lock holder is calling the server
    finish();
    await Promise.all([refreshA, refreshB]);
    expect(mocks.post).toHaveBeenCalledTimes(1);                           // B found the cookie fresh and did not call again
  });
});

describe("renewing the login before it expires (keep-alive)", () => {
  const MINUTE = 60_000;
  afterEach(() => { vi.useRealTimers(); });

  it("renews a login with no refresh on record, then leaves a young login alone", async () => {
    refreshWillSucceed();
    expect(loginNeedsRenewal()).toBe(true);
    await renewLoginIfStale();
    expect(mocks.post).toHaveBeenCalledTimes(1);
    expect(loginNeedsRenewal()).toBe(false);
    await renewLoginIfStale();
    expect(mocks.post).toHaveBeenCalledTimes(1);          // still young: no second request
  });

  it("renews again once the login is about 11 of its 15 minutes old", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-20T10:00:00Z"));
    refreshWillSucceed();
    await renewLoginIfStale();
    vi.setSystemTime(new Date("2026-11-20T10:10:00Z"));
    expect(loginNeedsRenewal()).toBe(false);              // 10 minutes: not yet
    vi.setSystemTime(new Date("2026-11-20T10:12:00Z"));
    expect(loginNeedsRenewal()).toBe(true);
    await renewLoginIfStale();
    expect(mocks.post).toHaveBeenCalledTimes(2);
    expect(MINUTE).toBe(60_000);
  });

  it("never throws, and a failed renewal leaves the next request to end the session properly", async () => {
    mocks.post.mockRejectedValue(networkFailure());
    await expect(renewLoginIfStale()).resolves.toBeUndefined();
    expect(isSessionKnownExpired()).toBe(false);
    expect(expiredEvents).toBe(0);
  });

  it("does nothing once the session is known to be over", async () => {
    mocks.post.mockRejectedValue(httpFailure(401));
    await expect(clientApi.get("/leave/requests/")).rejects.toBeTruthy();
    expect(isSessionKnownExpired()).toBe(true);
    mocks.post.mockClear();
    localStorage.clear();                                  // so the login would otherwise look stale
    await renewLoginIfStale();
    expect(mocks.post).not.toHaveBeenCalled();
  });
});
