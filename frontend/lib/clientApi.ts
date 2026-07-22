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

// ── Refresh mutex — one in-flight refresh, others queue ───────────────────────
let isRefreshing = false;
type QueueItem = { resolve: () => void; reject: (err: unknown) => void };
let refreshQueue: QueueItem[] = [];

function flushQueue(err: unknown, succeeded: boolean) {
  refreshQueue.forEach(({ resolve, reject }) =>
    succeeded ? resolve() : reject(err)
  );
  refreshQueue = [];
}

function dispatchSessionExpired() {
  isRefreshing = false;
  refreshQueue = [];
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
      await axios.post(
        `${API_BASE}/token/refresh/`,
        {},
        { withCredentials: true, headers: { "Content-Type": "application/json" } }
      );

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
