"use client";

import Modal from "@/components/Modal";
import type { Branch } from "@/app/dashboard/interview-list/_data";
import { RELATIONSHIP_OPTIONS, EMPTY_FORM } from "./_data";

interface ReferSomeoneModalProps {
  form: typeof EMPTY_FORM;
  setField: (key: keyof typeof EMPTY_FORM, value: string) => void;
  formError: string;
  saving: boolean;
  isAdmin: boolean;
  myBranch: string;
  branches: Branch[];
  onSubmit: (e: { preventDefault(): void }) => void;
  onClose: () => void;
}

export default function ReferSomeoneModal({
  form, setField, formError, saving, isAdmin, myBranch, branches, onSubmit, onClose,
}: ReferSomeoneModalProps) {
  return (
    <Modal
      title={<>Refer Someone<div style={{ fontSize: 12, color: "var(--on-variant)", margin: 0, fontWeight: 400 }}>Share a great candidate and earn a referral bonus</div></>}
      onClose={onClose}
      size="lg"
      maxWidth={680}
    >
          {formError && (
            <div className="alert alert-error" style={{ marginBottom: 20 }}>
              <i className="ti ti-alert-circle" /><div>{formError}</div>
            </div>
          )}

          <form onSubmit={onSubmit}>
            <p style={{ fontWeight: 700, fontSize: 11, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 16 }}>
              Candidate Information
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px 20px", marginBottom: 16 }}>
              <div className="field-group">
                <label className="field-label">Full Name <span style={{ color: "var(--error)" }}>*</span></label>
                <input className="field-input" placeholder="e.g. Rahul Sharma"
                  value={form.name} onChange={e => setField("name", e.target.value)}
                  required suppressHydrationWarning />
              </div>
              <div className="field-group">
                <label className="field-label">Email Address <span style={{ color: "var(--error)" }}>*</span></label>
                <input type="email" className="field-input" placeholder="candidate@email.com"
                  value={form.email} onChange={e => setField("email", e.target.value)}
                  required suppressHydrationWarning />
              </div>
              <div className="field-group">
                <label className="field-label">Phone Number</label>
                <input className="field-input" placeholder="+91 9876543210"
                  value={form.phone} onChange={e => setField("phone", e.target.value)}
                  suppressHydrationWarning />
              </div>
              <div className="field-group">
                <label className="field-label">Position Applied For <span style={{ color: "var(--error)" }}>*</span></label>
                <input className="field-input" placeholder="e.g. Senior Developer"
                  value={form.position_applied} onChange={e => setField("position_applied", e.target.value)}
                  required suppressHydrationWarning />
              </div>
              <div className="field-group">
                <label className="field-label">Company Code{isAdmin && <span style={{ color: "var(--error)" }}> *</span>}</label>
                {isAdmin ? (
                  <select
                    className="field-input field-select"
                    value={form.branch}
                    onChange={e => setField("branch", e.target.value)}
                    required
                    suppressHydrationWarning
                  >
                    <option value="">Select Company Code…</option>
                    {branches.map(b => <option key={b.id} value={String(b.id)}>{b.branch_name}</option>)}
                  </select>
                ) : (
                  <div className="field-input" style={{ background: "var(--bg)", color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 8, cursor: "default" }}>
                    <i className="ti ti-building" style={{ fontSize: 14, flexShrink: 0 }} />
                    {myBranch || "Not assigned"}
                  </div>
                )}
              </div>
              <div className="field-group">
                <label className="field-label">Your Relationship <span style={{ color: "var(--error)" }}>*</span></label>
                <select className="field-input field-select"
                  value={form.relationship} onChange={e => setField("relationship", e.target.value)}
                  required suppressHydrationWarning>
                  <option value="">Select relationship</option>
                  {RELATIONSHIP_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </div>
            <div className="field-group" style={{ marginBottom: 20 }}>
              <label className="field-label">Why would they be a great fit?</label>
              <textarea className="field-input" rows={3}
                placeholder="Share their experience, skills, and why you're recommending them…"
                value={form.notes} onChange={e => setField("notes", e.target.value)}
                suppressHydrationWarning style={{ resize: "vertical" }} />
            </div>
            <div className="alert alert-info" style={{ marginBottom: 20 }}>
              <i className="ti ti-info-circle" />
              <div>By submitting this referral you confirm the candidate has consented to share their information and has not applied in the last 12 months.</div>
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <button type="submit" className="btn btn-filled" disabled={saving} suppressHydrationWarning>
                {saving ? <><i className="ti ti-loader-2 spin" /> Submitting…</> : <><i className="ti ti-send" /> Submit Referral</>}
              </button>
              <button type="button" className="btn btn-ghost" onClick={onClose} suppressHydrationWarning>
                Cancel
              </button>
            </div>
          </form>
    </Modal>
  );
}
