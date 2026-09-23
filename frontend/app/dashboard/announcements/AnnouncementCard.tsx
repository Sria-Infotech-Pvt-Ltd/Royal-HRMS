"use client";

import { avatarColor, initials, timeAgo, CAT_BADGE, CAT_LABEL, type Announcement } from "./_data";

const BODY_PREVIEW = 220;

interface Props {
  ann: Announcement;
  onOpen: (ann: Announcement) => void;
  onEdit: (ann: Announcement) => void;
  onDelete: (id: number) => void;
  onToggleReact: (ann: Announcement) => void;
}

export default function AnnouncementCard({ ann, onOpen, onEdit, onDelete, onToggleReact }: Props) {
  const av = avatarColor(ann.posted_by_name);

  return (
    <div
      className={`ann-card${ann.is_pinned ? " pinned" : ""}`}
      onClick={() => onOpen(ann)}
    >
      <div className="ann-card-body">
        {/* ── Author row ─────────────────────────────────────── */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: "50%", flexShrink: 0,
            background: av.bg, color: av.color,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontWeight: 700, fontSize: 14,
          }}>
            {initials(ann.posted_by_name)}
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>{ann.posted_by_name}</span>
              {ann.posted_by_role && (
                <span style={{ fontSize: 11, color: "var(--on-variant)" }}>{ann.posted_by_role}</span>
              )}
              {ann.is_pinned && (
                <span className="badge badge-warn" style={{ fontSize: 10 }}>
                  <i className="ti ti-pin" /> Pinned
                </span>
              )}
              <span className={`badge ${CAT_BADGE[ann.category]}`} style={{ fontSize: 10, textTransform: "capitalize" }}>
                {CAT_LABEL[ann.category]}
              </span>
              {ann.visibility !== "all" && (
                <span className="badge badge-neutral" style={{ fontSize: 10 }}>
                  <i className={`ti ${ann.visibility === "department" ? "ti-sitemap" : "ti-building"}`} />
                  {" "}{ann.visibility === "department" ? ann.target_org_unit_name : ann.target_branch_name}
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>
              {timeAgo(ann.created_at)}
              {ann.updated_at !== ann.created_at && " · edited"}
            </div>
          </div>

          {ann.can_edit && (
            <div style={{ display: "flex", gap: 4, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
              <button className="btn btn-ghost btn-sm" title="Edit" onClick={() => onEdit(ann)} suppressHydrationWarning>
                <i className="ti ti-pencil" />
              </button>
              <button
                className="btn btn-ghost btn-sm"
                title="Delete"
                style={{ color: "var(--error)" }}
                onClick={() => onDelete(ann.id)}
                suppressHydrationWarning
              >
                <i className="ti ti-trash" />
              </button>
            </div>
          )}
        </div>

        {/* ── Title ─────────────────────────────────────────── */}
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>
          {ann.title}
        </div>

        {/* ── Body preview ─────────────────────────────────── */}
        <div className="ann-body-preview">
          {ann.body.length <= BODY_PREVIEW ? ann.body : ann.body.slice(0, BODY_PREVIEW) + "…"}
        </div>
        {ann.body.length > BODY_PREVIEW && (
          <span className="ann-read-more">Read more</span>
        )}

        {/* ── Footer ────────────────────────────────────────── */}
        <div className="ann-card-footer">
          <button
            onClick={e => { e.stopPropagation(); onToggleReact(ann); }}
            className={`ann-view-react-btn${ann.has_reacted ? " reacted" : ""}`}
            suppressHydrationWarning
          >
            <i className={`ti ${ann.has_reacted ? "ti-heart-filled" : "ti-heart"}`} style={{ fontSize: 16 }} />
            {ann.reactions_count > 0 && ann.reactions_count}
          </button>

          <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 13, color: "var(--on-variant)" }}>
            <i className="ti ti-eye" style={{ fontSize: 15 }} />
            {ann.views_count > 0 ? ann.views_count : "—"}
          </span>
        </div>
      </div>
    </div>
  );
}
