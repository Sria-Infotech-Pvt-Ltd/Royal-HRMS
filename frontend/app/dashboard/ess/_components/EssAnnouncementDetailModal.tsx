"use client";

// Read-only detail view of one announcement for the employee workspace.
// Opening it also records the view (once per announcement per browser), which
// the server uses to mark that announcement's bell notification as read.

import { useEffect } from "react";
import Modal from "@/components/Modal";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import {
  avatarColor, fullDateTime, initials, viewKey, CAT_BADGE, CAT_LABEL, type Announcement,
} from "../../announcements/_data";

interface Props {
  announcement: Announcement;
  /** Whether the signed-in person wrote it (an author's own opens are not counted as views). */
  isOwn: boolean;
  onToggleReact: (announcement: Announcement) => void;
  onClose: () => void;
}

export default function EssAnnouncementDetailModal({ announcement, isOwn, onToggleReact, onClose }: Props) {
  const avatar = avatarColor(announcement.posted_by_name);

  useEffect(() => {
    if (isOwn) return;
    const key = viewKey(announcement.id);
    try {
      if (localStorage.getItem(key)) return;
    } catch {
      return;
    }
    clientApi.post(API.announcements.view(announcement.id))
      .then(() => { try { localStorage.setItem(key, "1"); } catch { /* storage unavailable: just counts again next time */ } })
      .catch(() => { /* a failed view count must not block reading */ });
  }, [announcement.id, isOwn]);

  const audience = announcement.visibility === "all"
    ? "All Employees"
    : announcement.visibility === "department" ? announcement.target_org_unit_name : announcement.target_branch_name;

  return (
    <Modal
      title={<><i className="ti ti-speakerphone" /> Announcement</>}
      onClose={onClose}
      maxWidth="min(640px, 96vw)"
      footer={<button className="btn btn-filled" onClick={onClose} suppressHydrationWarning>Close</button>}
    >
      <div className="ann-view-author-row">
        <div style={{
          width: 40, height: 40, borderRadius: "50%", flexShrink: 0, background: avatar.bg, color: avatar.color,
          display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 14,
        }}>
          {initials(announcement.posted_by_name)}
        </div>
        <div>
          <div className="ann-view-name-row">
            <span style={{ fontWeight: 600, fontSize: 14 }}>{announcement.posted_by_name}</span>
            {announcement.posted_by_role && <span className="ann-view-role">{announcement.posted_by_role}</span>}
          </div>
          <div className="ann-view-timestamp">Posted {fullDateTime(announcement.created_at)}</div>
        </div>
      </div>

      <div className="ann-view-badges">
        {announcement.is_pinned && <span className="badge badge-warn"><i className="ti ti-pin" /> Pinned</span>}
        <span className={`badge ${CAT_BADGE[announcement.category]}`} style={{ textTransform: "capitalize" }}>
          {CAT_LABEL[announcement.category]}
        </span>
        <span className="badge badge-neutral"><i className="ti ti-users" /> {audience}</span>
      </div>

      <div className="ann-view-title">{announcement.title}</div>
      <div className="ann-view-body">{announcement.body}</div>

      <div className="ann-view-stats">
        <button
          className={`ann-view-react-btn${announcement.has_reacted ? " reacted" : ""}`}
          onClick={() => onToggleReact(announcement)}
          suppressHydrationWarning
        >
          <i className={`ti ${announcement.has_reacted ? "ti-heart-filled" : "ti-heart"}`} style={{ fontSize: 16 }} />
          {announcement.reactions_count > 0 ? announcement.reactions_count : "React"}
        </button>
      </div>
    </Modal>
  );
}
