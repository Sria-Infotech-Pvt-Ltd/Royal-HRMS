"use client";

import { useState } from "react";
import Link from "next/link";
import { useSharedAnnouncement } from "@/hooks/useEmployeeDashboard";

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export default function EmpAnnouncement() {
  const { data, loading } = useSharedAnnouncement();
  const [dismissed, setDismissed] = useState(false);

  if (loading || !data || dismissed) return null;

  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 12,
      padding: "11px 16px",
      borderRadius: 8,
      background: "rgba(30,78,140,0.07)",
      border: "1px solid rgba(30,78,140,0.18)",
    }}>
      <div style={{ width: 34, height: 34, borderRadius: 8, flexShrink: 0, background: "rgba(30,78,140,0.12)", color: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
        <i className={data.is_pinned ? "ti ti-pin" : "ti ti-speakerphone"} />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 2 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "var(--primary)", letterSpacing: "0.05em", textTransform: "uppercase" }}>
            {data.is_pinned ? "Pinned Announcement" : "Latest Announcement"}
          </span>
          {data.posted_by && (
            <span style={{ fontSize: 10, color: "var(--on-variant)" }}>
              {fmtDate(data.created_at)} · {data.posted_by}
            </span>
          )}
          {data.category && data.category !== "general" && (
            <span style={{ fontSize: 10, fontWeight: 600, padding: "1px 7px", borderRadius: 10, background: "rgba(30,78,140,0.12)", color: "var(--primary)" }}>
              {data.category.charAt(0).toUpperCase() + data.category.slice(1)}
            </span>
          )}
        </div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{data.title}</div>
        <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {data.body}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
        <Link href="/dashboard/announcements" style={{ fontSize: 12, color: "var(--primary)", fontWeight: 500, textDecoration: "none", whiteSpace: "nowrap" }}>
          View <i className="ti ti-arrow-right" style={{ fontSize: 11 }} />
        </Link>
        <button
          onClick={() => setDismissed(true)}
          style={{ background: "none", border: "none", cursor: "pointer", color: "var(--on-variant)", fontSize: 14, padding: "2px 4px", lineHeight: 1 }}
          aria-label="Dismiss announcement"
        >
          <i className="ti ti-x" />
        </button>
      </div>
    </div>
  );
}
