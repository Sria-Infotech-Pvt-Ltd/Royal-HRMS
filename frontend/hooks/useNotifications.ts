"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import { API_URL } from "@/lib/config";
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

function notificationsSocketUrl(): string | null {
  if (!API_URL) return null;
  const wsUrl = API_URL.replace(/^http/, "ws");
  return `${wsUrl}/ws/notifications/`;
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

  useEffect(() => {
    const url = notificationsSocketUrl();
    if (!url) return;

    let stopped = false;

    function connect() {
      if (stopped || !url) return;
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => {
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

      socket.onclose = () => {
        if (stopped) return;
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

    connect();

    return () => {
      stopped = true;
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
