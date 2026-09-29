"use client";

// Real "Drafts" popover — the reference mockup's own version only reads
// localStorage (browser-only, lost on a new device or after clearing
// storage). This lists the user's actual backend-persisted draft
// HireAction rows (GET /hire-actions/, added alongside its existing POST)
// so a draft genuinely survives across sessions/devices.

import { useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDateTime } from "@/lib/formatDate";

interface Draft {
  id: string;
  label: string;
  position_title: string;
  reserved_employee_id: string;
  updated_at: string;
}

export default function DraftsPopover({ onResume }: { onResume: (hireActionId: string) => void }) {
  const [open, setOpen] = useState(false);
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    clientApi.get<{ data: Draft[] }>(API.hireActions.list)
      .then(r => setDrafts(r.data.data ?? []))
      .catch(() => setDrafts([]));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function handleDelete(id: string) {
    if (!window.confirm("Discard this draft? This cannot be undone.")) return;
    try {
      await clientApi.delete(API.hireActions.detail(id));
      setDrafts(prev => prev?.filter(d => d.id !== id) ?? null);
    } catch {
      // best-effort — popover stays open, list unchanged on failure
    }
  }

  return (
    <span className="draftwrap" ref={ref}>
      <button className="btn btn-ghost" type="button" onClick={() => setOpen(v => !v)} suppressHydrationWarning>
        <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
          <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" />
        </svg>
        Drafts
        {drafts && drafts.length > 0 && <span className="cntbadge">{drafts.length}</span>}
      </button>
      {open && (
        <div className="draftpop">
          {drafts === null ? (
            <div className="draftempty">Loading…</div>
          ) : drafts.length === 0 ? (
            <div className="draftempty">No saved drafts yet. Start hiring someone and press <b>Save draft</b>.</div>
          ) : (
            drafts.map(d => (
              <div className="draftrow" key={d.id}>
                <div>
                  <b>{d.label}</b>
                  <span className="meta">
                    {d.position_title}{d.reserved_employee_id ? ` · ${d.reserved_employee_id}` : ""} ·{" "}
                    {formatDateTime(d.updated_at)}
                  </span>
                </div>
                <span className="acts">
                  <button className="btn btn-outline" onClick={() => { setOpen(false); onResume(d.id); }}>Resume</button>
                  <button className="mini" onClick={() => handleDelete(d.id)}>Delete</button>
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </span>
  );
}
