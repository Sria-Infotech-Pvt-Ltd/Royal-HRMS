"use client";

import { useState, useEffect, useCallback } from "react";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { API } from "@/lib/api/endpoints";
import type {
  Notification, NotificationListResponse, UnreadCountResponse,
} from "@/types/notifications";

const POLL_INTERVAL_MS = 60000;

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

  return { notifications, unreadCount, isLoading, fetchNotifications, markRead, markAllRead };
}
