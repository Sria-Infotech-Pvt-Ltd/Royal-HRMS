"use client";
import axios from "axios";
import type { AxiosError, InternalAxiosRequestConfig } from "axios";
import { API_BASE } from "./config";

// Deliberately a separate axios instance from clientApi (lib/clientApi.ts),
// not a shared one with different headers — platform-admin sessions run on
// an entirely different cookie/claim namespace (platform_access_token, not
// royal_access_token) and must never touch clientApi's tenant-session
// refresh queue, session-expired event, or clearAuth() logic.
const AUTH_URLS = ["/platform-admin/login/", "/platform-admin/token/refresh/"];

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

const platformAdminApi = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

platformAdminApi.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    const original = err.config as RetryConfig | undefined;
    if (
      err.response?.status !== 401 ||
      !original ||
      original._retry ||
      AUTH_URLS.some(u => original.url?.endsWith(u))
    ) {
      return Promise.reject(err);
    }

    original._retry = true;
    try {
      await axios.post(`${API_BASE}/platform-admin/token/refresh/`, {}, { withCredentials: true });
      return platformAdminApi(original);
    } catch (refreshErr) {
      if (typeof window !== "undefined") {
        window.location.href = "/platform-admin/login";
      }
      return Promise.reject(refreshErr);
    }
  }
);

export default platformAdminApi;
