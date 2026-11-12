"use client";

// Announcements for the employee workspace: everything visible to this person,
// newest and pinned first, filterable by category, opening in a read-only
// detail view. Posting and editing stay on the management page; nothing here
// changes an announcement except the reader's own like.

import { useEffect, useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getStoredUser } from "@/lib/auth";
import AnnouncementCard from "../../announcements/AnnouncementCard";
import { FILTERS, type Announcement, type PageMeta } from "../../announcements/_data";
import EssAnnouncementDetailModal from "./EssAnnouncementDetailModal";

interface Props {
  /** An announcement to open straight away, e.g. from its bell notification. */
  openAnnouncementId?: number | null;
}

const PAGE_SIZE = 10;

function noop() { /* employees cannot edit or delete from this tab */ }

export default function EssAnnouncementsTab({ openAnnouncementId = null }: Props) {
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(openAnnouncementId);
  const [reactedOverrides, setReactedOverrides] = useState<Record<number, { has_reacted: boolean; reactions_count: number }>>({});

  const listUrl = `${API.announcements.list}?page=${page}&page_size=${PAGE_SIZE}${category ? `&category=${category}` : ""}`;
  const { data: meta, loading, error, refetch } = useFetch<PageMeta>(listUrl);

  // The linked announcement may not be on the current page (or may be older than the list shows): fetch it by id.
  const { data: linked } = useFetch<Announcement>(openId ? API.announcements.detail(openId) : null);

  useEffect(() => { setOpenId(openAnnouncementId); }, [openAnnouncementId]);

  const currentUserId = useMemo(() => getStoredUser()?.userId ?? null, []);

  function withOverride(announcement: Announcement): Announcement {
    const override = reactedOverrides[announcement.id];
    // Employees never get edit/delete controls here, whatever the server says about the poster's rights.
    return { ...announcement, can_edit: false, ...(override ?? {}) };
  }

  async function toggleReact(announcement: Announcement) {
    const current = withOverride(announcement);
    const delta = current.has_reacted ? -1 : 1;
    setReactedOverrides(prev => ({
      ...prev,
      [announcement.id]: { has_reacted: !current.has_reacted, reactions_count: Math.max(0, current.reactions_count + delta) },
    }));
    try {
      await clientApi.post(API.announcements.react(announcement.id));
    } catch {
      setReactedOverrides(prev => { const next = { ...prev }; delete next[announcement.id]; return next; });
    }
  }

  const results = (meta?.results ?? []).map(withOverride);
  const opened = openId
    ? (results.find(a => a.id === openId) ?? (linked && linked.id === openId ? withOverride(linked) : null))
    : null;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Announcements</div>
          <div className="page-sub">Company news, policy updates and celebrations meant for you</div>
        </div>
      </div>

      <div className="ann-filter-bar">
        {FILTERS.map(filter => (
          <button
            key={filter.value}
            onClick={() => { setCategory(filter.value); setPage(1); }}
            className={`btn ${category === filter.value ? "btn-filled" : "btn-ghost"}`}
            suppressHydrationWarning
          >
            {filter.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> {error}{" "}
          <button className="btn btn-ghost btn-sm" onClick={refetch} suppressHydrationWarning>Retry</button>
        </div>
      )}

      {loading && !meta && (
        <div style={{ display: "flex", justifyContent: "center", padding: 60, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2" style={{ fontSize: 28, animation: "spin 1s linear infinite" }} />
        </div>
      )}

      {meta && results.length === 0 && (
        <div className="empty-state">
          <i className="ti ti-speakerphone" />
          <h3>No announcements</h3>
          <p>{category ? "Nothing in this category right now." : "You are all caught up."}</p>
        </div>
      )}

      {results.length > 0 && (
        <div className="ann-cards-list">
          {results.map(announcement => (
            <AnnouncementCard
              key={announcement.id}
              ann={announcement}
              onOpen={selected => setOpenId(selected.id)}
              onEdit={noop}
              onDelete={noop}
              onToggleReact={toggleReact}
            />
          ))}
        </div>
      )}

      {meta && meta.total_pages > 1 && (
        <div className="ann-pagination">
          <span className="ann-pagination-info">Page {meta.page} of {meta.total_pages}</span>
          <div className="ann-page-btns">
            <button className="btn btn-ghost btn-sm" disabled={meta.page <= 1} onClick={() => setPage(p => p - 1)} suppressHydrationWarning>
              <i className="ti ti-chevron-left" /> Prev
            </button>
            <button className="btn btn-ghost btn-sm" disabled={meta.page >= meta.total_pages} onClick={() => setPage(p => p + 1)} suppressHydrationWarning>
              Next <i className="ti ti-chevron-right" />
            </button>
          </div>
        </div>
      )}

      {opened && (
        <EssAnnouncementDetailModal
          announcement={opened}
          isOwn={opened.posted_by === currentUserId}
          onToggleReact={toggleReact}
          onClose={() => setOpenId(null)}
        />
      )}
    </div>
  );
}
