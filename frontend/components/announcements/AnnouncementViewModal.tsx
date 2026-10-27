"use client";

// Full announcement in a modal, opened from the dashboard "View" action.
// Always reads GET /announcements/<id>/ — the full post (never the dashboard's
// shortened preview), with the same audience rules as the Announcements page;
// it also records the view and marks that announcement's notification read.

import { useEffect } from "react";
import Modal from "@/components/Modal";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { audienceLabel, categoryLabel, viewState, type AnnouncementDetail } from "@/lib/announcementView";

const fmtDateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

export default function AnnouncementViewModal({ announcementId, onClose }: { announcementId: number | string; onClose: () => void }) {
  const { data, loading, error, status, refetch } = useFetch<AnnouncementDetail>(API.announcements.detail(announcementId));
  const view = viewState(data, loading, error, status);

  // Escape closes, like the backdrop and the Close button.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const title = view.kind === "ready" ? view.ann.title : "Announcement";

  return (
    <Modal
      title={<><i className="ti ti-speakerphone" style={{ marginRight: 8 }} />{title}</>}
      onClose={onClose}
      size="lg"
      scrollBody
      footer={
        <button className="btn btn-filled" onClick={onClose} autoFocus>
          Close
        </button>
      }
    >
      {view.kind === "loading" && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 0", color: "var(--on-variant)", fontSize: 13 }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading announcement…
        </div>
      )}

      {view.kind === "unavailable" && (
        <div className="alert alert-warn" style={{ marginBottom: 0 }}>
          <i className="ti ti-info-circle" />
          <span>This announcement is no longer available.</span>
        </div>
      )}

      {view.kind === "error" && (
        <div className="alert alert-error" style={{ marginBottom: 0, alignItems: "center" }}>
          <i className="ti ti-alert-circle" />
          <span style={{ flex: 1 }}>{view.message}</span>
          <button className="btn btn-ghost btn-sm" onClick={refetch}><i className="ti ti-refresh" /> Retry</button>
        </div>
      )}

      {view.kind === "ready" && (
        <article>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6, marginBottom: 12 }}>
            {view.ann.is_pinned && <span className="badge badge-warn"><i className="ti ti-pin" /> Pinned</span>}
            {view.ann.category && <span className="badge badge-primary">{categoryLabel(view.ann.category)}</span>}
            <span className="badge badge-neutral">
              <i className={`ti ${view.ann.visibility === "department" ? "ti-sitemap" : view.ann.visibility === "branch" ? "ti-building" : "ti-users"}`} />
              {" "}{audienceLabel(view.ann)}
            </span>
          </div>

          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginBottom: 16, display: "flex", flexWrap: "wrap", gap: "4px 12px" }}>
            <span><i className="ti ti-user" /> {view.ann.posted_by_name}{view.ann.posted_by_role ? ` · ${view.ann.posted_by_role}` : ""}</span>
            <span><i className="ti ti-calendar" /> {fmtDateTime(view.ann.created_at)}</span>
            {view.ann.updated_at !== view.ann.created_at && <span>(edited)</span>}
          </div>

          {/* Full text, line breaks and paragraphs kept (posts are plain text). */}
          <div style={{ fontSize: 14, lineHeight: 1.7, color: "var(--on-bg)", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            {view.ann.body}
          </div>
        </article>
      )}
    </Modal>
  );
}
