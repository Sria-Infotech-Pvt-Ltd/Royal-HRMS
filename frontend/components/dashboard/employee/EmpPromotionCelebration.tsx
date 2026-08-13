"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import type { Notification, NotificationListResponse } from "@/types/notifications";

// Source of truth is the persisted Notification row (created server-side by
// the promotion signal handler), not local component state — this widget
// only ever renders what /api/notifications/ currently reports as an
// unread promotion notification, and "dismiss" persists via the same
// mark-as-read endpoint NotificationBell already uses, so the celebration
// correctly stays gone after a refresh/relogin instead of just hiding locally.
export default function EmpPromotionCelebration() {
  const { data, loading, refetch } = useFetch<NotificationListResponse>(
    `${API.notifications.list}?notification_type=promotion&is_read=false&page_size=1`
  );
  const [dismissing, setDismissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const notification: Notification | undefined = data?.results?.[0];

  if (loading || !notification) return null;

  async function dismiss() {
    setDismissing(true);
    setError(null);
    try {
      await clientApi.patch(API.notifications.markRead(notification!.id));
      refetch();
    } catch {
      setError("Couldn't dismiss — please try again.");
    } finally {
      setDismissing(false);
    }
  }

  return (
    <div
      className="mb-16"
      style={{
        padding: "16px 20px",
        borderRadius: 10,
        background: "linear-gradient(135deg, rgba(27,138,107,0.10), rgba(30,78,140,0.06))",
        border: "1px solid rgba(27,138,107,0.25)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 20 }}>🎉</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: "var(--on-bg)" }}>
              {notification.title}
            </span>
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginLeft: 28 }}>
            {notification.message}
          </div>
          {error && (
            <div style={{ fontSize: 11, color: "var(--error)", marginLeft: 28, marginTop: 4 }}>{error}</div>
          )}
        </div>
        <button
          className="btn btn-ghost btn-sm"
          onClick={dismiss}
          disabled={dismissing}
          style={{ flexShrink: 0 }}
        >
          {dismissing ? "…" : "Got it"}
        </button>
      </div>
    </div>
  );
}
