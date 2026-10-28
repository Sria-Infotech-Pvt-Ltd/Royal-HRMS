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
import ConfirmModal from "@/components/ConfirmModal";
import { useToast } from "@/components/ToastProvider";
import { useApiErrors } from "@/hooks/useApiErrors";

interface Draft {
  id: string;
  label: string;
  position_title: string;
  reserved_employee_id: string;
  updated_at: string;
  /** Non-blank when the draft looks like someone who already is an employee (a stale or test leftover). */
  existing_employee_match?: string;
}

export default function DraftsPopover({ onResume }: { onResume: (hireActionId: string) => void }) {
  const [open, setOpen] = useState(false);
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const { showToast } = useToast();
  const { handleError } = useApiErrors();
  const [draftToDelete, setDraftToDelete] = useState<Draft | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

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

  async function confirmDelete(draft: Draft) {
    setIsDeleting(true);
    try {
      await clientApi.delete(API.hireActions.detail(draft.id));
      setDrafts(prev => prev?.filter(d => d.id !== draft.id) ?? null);
      showToast("Draft discarded.", "success");
      setDraftToDelete(null);
    } catch (err: unknown) {
      handleError(err, "Could not discard the draft.");
    } finally {
      setIsDeleting(false);
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
                  {d.existing_employee_match && (
                    <span className="meta" style={{ color: "var(--warn)" }}>Possible leftover: {d.existing_employee_match}</span>
                  )}
                </div>
                <span className="acts">
                  <button className="btn btn-outline" onClick={() => { setOpen(false); onResume(d.id); }}>Resume</button>
                  <button className="mini" onClick={() => setDraftToDelete(d)}>Discard</button>
                </span>
              </div>
            ))
          )}
        </div>
      )}
      {draftToDelete && (
        <ConfirmModal
          title="Discard this draft?"
          body={`The draft for ${draftToDelete.label} will be deleted${draftToDelete.reserved_employee_id ? ` and employee number ${draftToDelete.reserved_employee_id} released` : ""}. This cannot be undone.`}
          confirmLabel="Discard draft"
          danger
          saving={isDeleting}
          onConfirm={() => confirmDelete(draftToDelete)}
          onCancel={() => setDraftToDelete(null)}
        />
      )}
    </span>
  );
}
