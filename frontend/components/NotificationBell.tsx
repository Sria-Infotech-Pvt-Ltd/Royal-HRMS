"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useNotifications } from "@/hooks/useNotifications";
import type { Notification, NotificationModule } from "@/types/notifications";

const MODULE_ROUTES: Record<NotificationModule, string> = {
  leave:          "/dashboard/leave",
  attendance:     "/dashboard/my-attendance",
  regularization: "/dashboard/my-attendance",
  announcement:   "/dashboard/announcements",
  holiday:        "/dashboard/attendance",
  permission:     "/dashboard/leave",
  promotion:      "/dashboard/profile",
};

function relativeTime(iso: string): string {
  const diffSec = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (diffSec < 60) return "Just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hr ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay === 1) return "Yesterday";
  if (diffDay < 7) return `${diffDay} days ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function NotificationBell() {
  const router = useRouter();
  const {
    notifications, unreadCount, isLoading, fetchNotifications, markRead, markAllRead,
  } = useNotifications();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) fetchNotifications();
  }, [open, fetchNotifications]);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  async function handleRowClick(n: Notification) {
    setOpen(false);
    if (!n.is_read) await markRead(n.id);
    router.push(MODULE_ROUTES[n.module] ?? "/dashboard");
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        className="relative w-[34px] h-[34px] rounded-lg flex items-center justify-center bg-transparent text-[var(--outline)] border-none cursor-pointer hover:bg-[var(--bg-mid)]"
        title="Notifications"
        onClick={() => setOpen(v => !v)}
        suppressHydrationWarning
      >
        <i className="ti ti-bell text-[18px]" />
        {unreadCount > 0 && (
          <span className="absolute top-[2px] right-[2px] min-w-[16px] h-[16px] px-[3px] rounded-full flex items-center justify-center text-[9px] font-bold text-white bg-[var(--error)] border-[1.5px] border-white">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-[42px] w-[340px] bg-white rounded-xl border border-[var(--outline-v)] shadow-lg z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--outline-v)]">
            <span className="text-sm font-semibold text-[var(--on-bg)]">Notifications</span>
            {unreadCount > 0 && (
              <button
                className="text-xs font-medium text-[var(--primary)] bg-transparent border-none cursor-pointer hover:underline"
                onClick={markAllRead}
              >
                Mark all as read
              </button>
            )}
          </div>

          <div className="max-h-[380px] overflow-y-auto divide-y divide-[var(--outline-v)]">
            {isLoading ? (
              <div className="flex items-center justify-center py-10">
                <i className="ti ti-loader-2" style={{ fontSize: 22, color: "var(--outline)", animation: "spin 1s linear infinite" }} />
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-10 text-center text-sm text-[var(--on-variant)]">
                No notifications yet
              </div>
            ) : (
              notifications.map(n => (
                <button
                  key={n.id}
                  onClick={() => handleRowClick(n)}
                  className="flex items-start gap-3 w-full px-4 py-3 text-left bg-transparent border-none cursor-pointer hover:bg-[var(--bg-mid)]"
                >
                  <span
                    className="mt-[5px] w-2 h-2 rounded-full flex-shrink-0"
                    style={{ background: n.is_read ? "transparent" : "var(--primary)" }}
                  />
                  <span className="flex-1 min-w-0">
                    <span
                      className="block text-[13px] text-[var(--on-bg)]"
                      style={{ fontWeight: n.is_read ? 400 : 600 }}
                    >
                      {n.title}
                    </span>
                    <span
                      className="block text-xs text-[var(--on-variant)] mt-0.5"
                      style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}
                    >
                      {n.message}
                    </span>
                    <span className="block text-[11px] text-[var(--outline)] mt-1">
                      {relativeTime(n.created_at)}
                    </span>
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
