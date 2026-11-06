"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import { API_URL, API_BASE } from "@/lib/config";
import type {
  Notification, NotificationListResponse, UnreadCountResponse,
} from "@/types/notifications";
import type { HRActionQueue, LeaveUpdatePayload } from "@/types/dashboard";

// Poll stays on as a fallback (the socket carries live updates when
// connected; the cookie-authenticated handshake can fail on flaky
// networks/proxies where a plain XHR poll still works).
const POLL_INTERVAL_MS = 60000;
const WS_RECONNECT_BASE_MS = 1000;
const WS_RECONNECT_MAX_MS  = 30000;
// A socket that never opens (proxy without WebSocket support, rejected
// login) must not be retried forever — production logged ~277k such
// attempts. After this many consecutive failed opens, live updates stop for
// this page and the 60s poll carries on; going back online retries once more.
const WS_MAX_FAILED_OPENS  = 5;
// Close codes the server uses for "will never accept this" (see
// apps.notifications.consumers): 4401 not signed in, 4004 unknown path.
const WS_FATAL_CLOSE_CODES = new Set([4401, 4004]);
// Refreshing on every single reconnect attempt (previously unconditional)
// means a socket that keeps failing to open — a flaky backend/proxy, or an
// environment where the WS handshake never succeeds at all — hammers
// /token/refresh/ every 1-30s forever, rotating the refresh token each time
// for no reason (the cookie was never actually close to expiring). Only
// refresh if it's been at least this long since the last one; 10 minutes
// stays safely under the 15-minute access-token lifetime this guard exists
// for in the first place.
const REFRESH_COOLDOWN_MS = 10 * 60 * 1000;

// The handshake authenticates with the httpOnly access-token cookie, which
// the browser only holds for the site the user signed in on (logins go
// through this site's own /api proxy). So in production the socket must use
// the same host as the page — e.g. wss://royalhrms.com/ws/notifications/,
// routed to Daphne by nginx — not the separate API host, which never gets
// the cookie. NEXT_PUBLIC_WS_URL overrides; local dev keeps using API_URL.
export function notificationsSocketUrl(): string | null {
  const explicit = process.env.NEXT_PUBLIC_WS_URL;
  if (explicit) return `${explicit.replace(/\/+$/, "")}/ws/notifications/`;
  if (typeof window !== "undefined" && process.env.NODE_ENV === "production") {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    return `${scheme}://${window.location.host}/ws/notifications/`;
  }
  if (!API_URL) return null;
  return `${API_URL.replace(/^http/, "ws")}/ws/notifications/`;
}

// The httpOnly access-token cookie the WS handshake authenticates with
// (see apps.notifications.ws_auth.CookieJWTAuthMiddleware) expires every 15
// minutes and is otherwise only refreshed by the 60s unread-count poll below
// — but browsers throttle setInterval on backgrounded tabs, so that poll can
// stall well past 15 minutes. Reconnecting after that with the stale cookie
// gets rejected (WSREJECT) even though the session is still perfectly valid.
// Refreshing right before each (re)connect attempt closes that gap.
function refreshTokenSilently(): Promise<void> {
  return axios
    .post(`${API_BASE}/token/refresh/`, {}, { withCredentials: true, headers: { "Content-Type": "application/json" } })
    .then(() => undefined)
    .catch(() => undefined);
}

export function useNotifications() {
  const { showToast } = useToast();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount,   setUnreadCount]   = useState(0);
  const [isLoading,     setIsLoading]     = useState(false);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const res = await clientApi.get<{ data: UnreadCountResponse }>(API.notifications.unreadCount);
      setUnreadCount(res.data.data.unread_count);
    } catch {
      // silently handled — a failed background poll should not disrupt the UI
    }
  }, []);

  const fetchNotifications = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await clientApi.get<{ data: NotificationListResponse }>(
        API.notifications.list,
        { params: { page_size: 20 } }
      );
      const results = res.data.data.results;
      setNotifications(results);
      // Derive the badge count from the rows actually on screen, not the
      // response's separate unread_count field — the list is the ground
      // truth for what the panel shows, so the badge can never drift from it.
      setUnreadCount(results.filter(n => !n.is_read).length);
    } catch {
      // silently handled — panel falls back to its empty state
    } finally {
      setIsLoading(false);
    }
  }, []);

  const markRead = useCallback(async (id: string) => {
    try {
      await clientApi.patch(API.notifications.markRead(id));
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch {
      // silently handled
    }
  }, []);

  const markAllRead = useCallback(async () => {
    try {
      const res = await clientApi.patch<{ message: string }>(API.notifications.markAllRead);
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
      showToast(res.data.message, "success");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to mark notifications as read.", "error");
    }
  }, [showToast]);

  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // ─── Live updates over WebSocket ───────────────────────────────────────────
  // The socket is additive: on top of the poll above, it pushes new
  // notifications the instant the backend creates them (see
  // apps.notifications.signals._push_live). A dropped/failed connection just
  // means the existing 60s poll is all that's left — never a hard failure.
  const reconnectAttempt = useRef(0);
  const reconnectTimer   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const socketRef        = useRef<WebSocket | null>(null);
  const lastRefreshAt    = useRef(0);

  useEffect(() => {
    const url = notificationsSocketUrl();
    if (!url) return;

    let stopped = false;
    let failedOpens = 0;      // consecutive attempts that never reached onopen
    let givenUp = false;

    function connect() {
      if (stopped) return;
      // Refresh the access-token cookie before a (re)connect attempt, but
      // only if it's actually been long enough that the cookie could be
      // stale — see REFRESH_COOLDOWN_MS above. Best-effort: if it fails,
      // fall through and try the handshake anyway (matching prior behavior).
      if (Date.now() - lastRefreshAt.current < REFRESH_COOLDOWN_MS) {
        openSocket();
        return;
      }
      refreshTokenSilently().then(() => {
        if (stopped) return;
        lastRefreshAt.current = Date.now();
        openSocket();
      });
    }

    function openSocket() {
      const socket = new WebSocket(url as string);
      socketRef.current = socket;
      let opened = false;

      socket.onopen = () => {
        opened = true;
        failedOpens = 0;
        reconnectAttempt.current = 0;
      };

      socket.onmessage = event => {
        try {
          const payload = JSON.parse(event.data as string);
          if (payload?.type === "attendance_update") {
            window.dispatchEvent(new CustomEvent("attendance:updated"));
            return;
          }
          if (payload?.type === "leave_update") {
            // payload is JSON.parse output (any). Narrow to the shape push_leave_update
            // (backend/apps/dashboard/views/overview.py) always sends.
            const frame = payload as { action_queue?: HRActionQueue; pending_actions?: number };
            const detail: LeaveUpdatePayload = {
              action_queue:    frame.action_queue    ?? null,
              pending_actions: typeof frame.pending_actions === "number" ? frame.pending_actions : null,
            };
            window.dispatchEvent(new CustomEvent<LeaveUpdatePayload>("leave:updated", { detail }));
            return;
          }
          if (payload?.type !== "notification" || !payload.notification) return;
          const incoming = payload.notification as Notification;
          setNotifications(prev =>
            prev.some(n => n.id === incoming.id) ? prev : [incoming, ...prev]
          );
          setUnreadCount(prev => prev + 1);
          showToast(incoming.title, "info");
        } catch {
          // malformed frame — ignore, next message (or the poll) will catch up
        }
      };

      socket.onclose = (event: CloseEvent) => {
        if (stopped) return;
        if (!opened || WS_FATAL_CLOSE_CODES.has(event.code)) {
          failedOpens += 1;
          // A rejected login gets one more try (the cookie may just have been
          // refreshed); anything that keeps failing stops here — polling stays.
          const fatal = WS_FATAL_CLOSE_CODES.has(event.code) && failedOpens > 1;
          if (fatal || failedOpens >= WS_MAX_FAILED_OPENS) {
            givenUp = true;
            return;
          }
          if (WS_FATAL_CLOSE_CODES.has(event.code)) lastRefreshAt.current = 0;   // force a token refresh
        }
        const delay = Math.min(
          WS_RECONNECT_BASE_MS * 2 ** reconnectAttempt.current,
          WS_RECONNECT_MAX_MS
        );
        reconnectAttempt.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      };

      // Guard with stopped: if cleanup already ran, don't initiate another close
      // (which would re-enter onclose and schedule a reconnect on a dead instance).
      socket.onerror = () => {
        if (!stopped) socket.close();
      };
    }

    // Back online after giving up (e.g. phone switched networks): try again.
    function onOnline() {
      if (stopped || !givenUp) return;
      givenUp = false;
      failedOpens = 0;
      reconnectAttempt.current = 0;
      connect();
    }
    window.addEventListener("online", onOnline);

    connect();

    return () => {
      stopped = true;
      window.removeEventListener("online", onOnline);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      // Null out handlers before closing so the browser's close event on a
      // CONNECTING socket doesn't re-enter onclose/onerror and schedule a
      // reconnect or log a spurious error (React StrictMode double-invoke).
      const sock = socketRef.current;
      if (sock) {
        sock.onopen    = null;
        sock.onmessage = null;
        sock.onerror   = null;
        sock.onclose   = null;
        sock.close();
        socketRef.current = null;
      }
    };
  }, [showToast]);

  return { notifications, unreadCount, isLoading, fetchNotifications, markRead, markAllRead };
}
