"use client";

// Platform Admin in-app notifications (new / paid website registrations).
// Polls the unread count every 60 s; opening marks what is shown as read.

import { useEffect, useRef, useState } from "react";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { PlatformNotification } from "@/types/platformAdmin";

export default function NotificationBell() {
  const [items, setItems] = useState<PlatformNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  async function load() {
    try {
      const { data } = await platformAdminApi.get(API.platformAdmin.notifications);
      setItems(data.data.results);
      setUnread(data.data.unread_count);
    } catch {
      /* the bell is best-effort */
    }
  }

  useEffect(() => {
    void load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) {
      try {
        await platformAdminApi.post(API.platformAdmin.notificationsRead, { all: true });
        setUnread(0);
      } catch { /* ignore */ }
    }
  }

  return (
    <div ref={boxRef} style={{ position: "relative" }}>
      <button className="btn btn-ghost btn-sm" onClick={toggle} aria-label={`Notifications (${unread} unread)`}
        style={{ position: "relative" }}>
        <i className="ti ti-bell" style={{ fontSize: 18 }} />
        {unread > 0 && (
          <span style={{ position: "absolute", top: 0, right: 0, minWidth: 16, height: 16, borderRadius: 8, fontSize: 10,
            background: "var(--error)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", padding: "0 4px" }}>
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="card" style={{ position: "absolute", right: 0, top: "110%", width: 340, maxHeight: 420, overflowY: "auto",
          zIndex: 50, boxShadow: "var(--shadow-md)", padding: 8 }}>
          {items.length === 0 ? <div style={{ padding: 12, fontSize: 13, color: "var(--on-variant)" }}>No notifications.</div> :
            items.map(n => (
              <a key={n.id} href={n.link || "#"} style={{ display: "block", padding: "8px 10px", borderRadius: 8, textDecoration: "none",
                background: n.is_read ? "transparent" : "var(--bg-low)", color: "var(--on-bg)" }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{n.title}</div>
                {n.message && <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{n.message}</div>}
                <div style={{ fontSize: 11, color: "var(--outline)" }}>{new Date(n.created_at).toLocaleString("en-IN")}</div>
              </a>
            ))}
        </div>
      )}
    </div>
  );
}
