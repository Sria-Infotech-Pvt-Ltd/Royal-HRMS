"use client";

// Manager-review action for the HR queue — HR holds performance.manage_cycles,
// so the backend (ManagerReviewDetailView/SubmitManagerReviewView) lets them
// act on any employee's review the same way the actual reporting manager
// would, which is what makes an "HR review queue" possible at all.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { ApiReview } from "../_client";

interface Props {
  review: ApiReview;
  onClose: () => void;
  onSaved: () => void;
}

export default function ReviewActionModal({ review, onClose, onSaved }: Props) {
  const [rating, setRating] = useState(review.manager_rating || "");
  const [notes, setNotes] = useState(review.manager_notes || "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSubmit() {
    setErr(null);
    setSaving(true);
    try {
      await clientApi.patch(API.performance.reviewDetail(review.id), { manager_rating: rating, manager_notes: notes });
      await clientApi.post(API.performance.submitManagerReview(review.id));
      onSaved();
    } catch (error: unknown) {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setErr(msg ?? "Failed to submit manager review.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ width: "min(560px, 95vw)" }}>
        <div className="modal-header">
          <div className="modal-title">Manager review — {review.employee_name}</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          {err && <div className="alert alert-error mb-16">{err}</div>}

          <h4 style={{ fontSize: "0.9rem", marginBottom: 10 }}>Self-review</h4>
          <div style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 16, display: "grid", gap: 6 }}>
            <div><strong>Key strengths:</strong> {review.key_strengths || "—"}</div>
            <div><strong>Development areas:</strong> {review.development_areas || "—"}</div>
            <div><strong>Support needed:</strong> {review.support_needed || "—"}</div>
            <div><strong>Self rating:</strong> {review.self_rating || "—"}</div>
          </div>

          <h4 style={{ fontSize: "0.9rem", marginBottom: 10 }}>Manager review</h4>
          <div className="field-group mb-16">
            <label className="field-label">Rating (1-5)</label>
            <select className="field-input field-select" value={rating} onChange={e => setRating(e.target.value)}>
              <option value="">— Select —</option>
              {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Notes</label>
            <textarea className="field-input" rows={3} value={notes} onChange={e => setNotes(e.target.value)} />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={saving || !rating}>
            {saving ? "Submitting…" : "Submit Review"}
          </button>
        </div>
      </div>
    </div>
  );
}
