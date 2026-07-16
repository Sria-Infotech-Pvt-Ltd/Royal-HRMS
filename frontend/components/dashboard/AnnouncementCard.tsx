"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AnnouncementData } from "@/types/dashboard";

function formatDate(raw: string | undefined): string {
  if (!raw) return "";
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function resolveAuthor(data: AnnouncementData): string {
  if (!data.created_by) return data.author ?? "";
  if (typeof data.created_by === "string") return data.created_by;
  return data.created_by.name ?? "";
}

export default function AnnouncementCard() {
  const { data, loading } = useFetch<AnnouncementData>(API.dashboard.announcement);

  const isValidAnnouncement =
    data !== null &&
    typeof data === "object" &&
    "title" in data;

  const announcement = isValidAnnouncement ? data : null;
  const body = announcement?.body ?? announcement?.content ?? "";
  const dateStr = formatDate(announcement?.created_at ?? announcement?.posted_on);
  const author = announcement ? resolveAuthor(announcement) : "";

  return (
    <div className="card mb-16">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-speakerphone" /> Latest Announcement</div>
        {!loading && announcement && (
          <a href="/dashboard/announcements" className="btn btn-ghost btn-sm">
            All <i className="ti ti-arrow-right" style={{ fontSize: 11, marginLeft: 3 }} />
          </a>
        )}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : !announcement ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-speakerphone" style={{ fontSize: 22, display: "block", marginBottom: 6, opacity: 0.3 }} />
          No announcements
        </div>
      ) : (
        <div style={{ padding: "16px 20px" }}>
          {announcement.category && (
            <span style={{
              display: "inline-block", fontSize: 10, fontWeight: 700,
              padding: "2px 8px", borderRadius: 4, marginBottom: 8,
              background: "rgba(30,78,140,0.10)", color: "var(--primary)",
              letterSpacing: "0.05em", textTransform: "uppercase",
            }}>
              {announcement.category}
            </span>
          )}
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--on-bg)", lineHeight: 1.4, marginBottom: 8 }}>
            {announcement.title}
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", lineHeight: 1.6, marginBottom: 12 }}>
            {body}
          </div>
          {(dateStr || author) && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: "var(--on-variant)" }}>
              {author && (
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <i className="ti ti-user" style={{ fontSize: 10 }} />{author}
                </span>
              )}
              {dateStr && author && <span style={{ opacity: 0.4 }}>·</span>}
              {dateStr && (
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <i className="ti ti-calendar" style={{ fontSize: 10 }} />{dateStr}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
