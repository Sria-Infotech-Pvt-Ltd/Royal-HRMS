"use client";
import axios from "axios";
import type { AxiosError, InternalAxiosRequestConfig } from "axios";
import { API_BASE } from "./config";
import { clearAuth } from "./auth";

// Endpoints that must never trigger a silent refresh on 401
const AUTH_URLS = [
  "/login/",
  "/token/refresh/",
  "/forgot-password/",
  "/verify-otp/",
  "/reset-password/",
];

// Set to true during intentional logout so in-flight 401s don't show the
// session-expired overlay after the user has already chosen to sign out.
let _intentionalLogout = false;
export function markIntentionalLogout() { _intentionalLogout = true; }

// Set to true once a refresh attempt has actually failed. Without this,
// every widget still mounted during the few seconds between "session expired"
// and the redirect to /login (dashboard pages fire many concurrent requests)
// independently retries the refresh call and 401s again, hammering
// /token/refresh/ in a burst. Reset on the next successful login.
let _sessionKnownExpired = false;
export function resetSessionExpired() { _sessionKnownExpired = false; }

const clientApi = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// ── Request: fix FormData Content-Type ────────────────────────────────────────
clientApi.interceptors.request.use((config) => {
  // When the body is FormData, remove the default Content-Type so the browser
  // can set multipart/form-data with the correct boundary automatically.
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

// ── Refresh mutex — one in-flight refresh per tab, others queue ────────────────
let isRefreshing = false;
type QueueItem = { resolve: () => void; reject: (err: unknown) => void };
let refreshQueue: QueueItem[] = [];

function flushQueue(err: unknown, succeeded: boolean) {
  refreshQueue.forEach(({ resolve, reject }) =>
    succeeded ? resolve() : reject(err)
  );
  refreshQueue = [];
}

// ── Cross-tab refresh coordination ─────────────────────────────────────────────
// The mutex above only serializes refreshes within one tab's JS context. The
// backend rotates the refresh token cookie on every use and blacklists the old
// one (SIMPLE_JWT ROTATE_REFRESH_TOKENS/BLACKLIST_AFTER_ROTATION, settings.py)
// — with two tabs/windows of the dashboard open, both can have their access
// token expire around the same moment, both call /token/refresh/, and whichever
// request the server processes second is carrying a refresh token the first
// request already rotated out, so it gets rejected with 401 even though the
// session is genuinely still valid. That looked like a real bug report (a
// refresh token failing well before its real 7-day lifetime) and traces back
// to exactly this race, not an actual expired/invalid session.
//
// navigator.locks serializes the critical section across every tab of this
// origin, not just this module instance, so only one tab ever calls
// /token/refresh/ at a time. A tab that was waiting on the lock then checks
// whether another tab already refreshed in roughly the last few seconds —
// if so its own cookie is already fresh (cookies are shared browser-wide), so
// it skips calling refresh again and just retries the original request.
const REFRESH_LOCK_NAME = "royal-hrms-token-refresh";
const LAST_REFRESH_KEY = "royal_hrms_last_token_refresh_at";
const RECENT_REFRESH_WINDOW_MS = 4000;

function recentlyRefreshedElsewhere(): boolean {
  try {
    const last = Number(localStorage.getItem(LAST_REFRESH_KEY) ?? "0");
    return Date.now() - last < RECENT_REFRESH_WINDOW_MS;
  } catch {
    return false; // localStorage unavailable (private mode, etc.) — never skip on its account
  }
}

function markRefreshedNow(): void {
  try { localStorage.setItem(LAST_REFRESH_KEY, String(Date.now())); } catch { /* best-effort */ }
}

async function callTokenRefresh(): Promise<void> {
  if (recentlyRefreshedElsewhere()) return;
  await axios.post(
    `${API_BASE}/token/refresh/`,
    {},
    { withCredentials: true, headers: { "Content-Type": "application/json" } }
  );
  markRefreshedNow();
}

function refreshAccessToken(): Promise<void> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  if (locks) {
    return locks.request<void>(REFRESH_LOCK_NAME, () => callTokenRefresh());
  }
  return callTokenRefresh();
}

function dispatchSessionExpired() {
  isRefreshing = false;
  refreshQueue = [];
  _sessionKnownExpired = true;
  clearAuth();
  if (typeof window !== "undefined" && !_intentionalLogout) {
    window.dispatchEvent(new CustomEvent("session:expired"));
  }
}

// ── Response: silent refresh on 401, session-expired on refresh failure ────────
type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

clientApi.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    const original = err.config as RetryConfig | undefined;

    // Pass through: non-401, already-retried, or auth endpoints
    if (
      err.response?.status !== 401 ||
      !original ||
      original._retry ||
      AUTH_URLS.some(u => original.url?.endsWith(u))
    ) {
      return Promise.reject(normaliseError(await resolveBlobErrorData(err)));
    }

    // The session is already known dead (a prior refresh attempt failed) —
    // don't spend another round-trip on /token/refresh/ for every request
    // still in flight while the app finishes redirecting to /login.
    if (_sessionKnownExpired) {
      return Promise.reject(normaliseError(await resolveBlobErrorData(err)));
    }

    // Queue behind an in-flight refresh
    if (isRefreshing) {
      original._retry = true;
      return new Promise((resolve, reject) => {
        refreshQueue.push({
          resolve: () => resolve(clientApi(original)),
          reject,
        });
      });
    }

    original._retry = true;
    isRefreshing = true;

    try {
      // The httpOnly refresh token cookie is sent automatically via withCredentials.
      await refreshAccessToken();

      flushQueue(null, true);
      return clientApi(original);
    } catch (refreshErr) {
      flushQueue(refreshErr, false);
      dispatchSessionExpired();
      return Promise.reject(normaliseError(refreshErr));
    } finally {
      isRefreshing = false;
    }
  }
);

// ── Unwrap blob error bodies ───────────────────────────────────────────────────
// Requests made with responseType: "blob" (file downloads) still get their
// error body delivered as a Blob even when the backend returned JSON (e.g. a
// 403 on a sample-file endpoint) — normaliseError below can't read `.message`
// off a Blob, so every blob-download call site silently fell back to axios's
// generic "Request failed with status code 403" instead of the real reason.
// Root-cause fix here rather than at each blob-download call site, matching
// how normaliseError itself was already fixed once for the same reason.
async function resolveBlobErrorData(err: AxiosError): Promise<AxiosError> {
  const data = err.response?.data;
  if (!(data instanceof Blob)) return err;
  try {
    const text = await data.text();
    const parsed = JSON.parse(text);
    return { ...err, response: { ...err.response, data: parsed } } as AxiosError;
  } catch {
    return err;
  }
}

// ── Normalise error shape for all callers ─────────────────────────────────────
function normaliseError(err: unknown) {
  const e = err as AxiosError<{ message?: string; error?: string; data?: unknown }>;
  const message =
    e?.response?.data?.message ??
    e?.response?.data?.error ??
    (e as { message?: string })?.message ??
    "An unexpected error occurred.";
  const status = e?.response?.status ?? 500;
  // Preserve field-level validation errors (e.g. 422 responses with data.{field: [msg]})
  const data = e?.response?.data?.data;
  // Keep `response.data.message` too — every existing catch block across the app
  // reads that shape (the raw axios shape). Without it, this normalised object
  // has no `.response`, so those reads silently return undefined and fall back
  // to a generic message no matter what the backend actually said.
  return { message, status, data, response: { data: { message, data } } };
}

export default clientApi;
