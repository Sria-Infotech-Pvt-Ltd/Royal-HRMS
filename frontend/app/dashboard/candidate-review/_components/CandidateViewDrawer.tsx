"use client";

import { Candidate, fmtDate } from "../../interview-list/_data";

interface Props {
  candidate: Candidate;
  onClose:   () => void;
}

function Row({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: ".3rem 0", fontSize: ".85rem", borderBottom: "1px solid var(--outline-v)" }}>
      <span style={{ color: "var(--on-variant)" }}>{label}</span>
      <span style={{ fontWeight: 500, textAlign: "right", maxWidth: "60%" }}>{value}</span>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return (
    <div style={{ fontWeight: 700, fontSize: ".8rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--on-variant)", marginBottom: ".5rem", marginTop: "1.25rem" }}>
      {title}
    </div>
  );
}

export default function CandidateViewDrawer({ candidate, onClose }: Props) {
  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 500 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">Candidate — {candidate.name}</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body">
          <SectionTitle title="Application Info" />
          <Row label="Email"            value={candidate.email} />
          <Row label="Phone"            value={candidate.phone} />
          <Row label="Position Applied" value={candidate.position_applied} />
          <Row label="Branch"           value={candidate.branch_name} />
          <Row label="Status"           value={candidate.status} />
          <Row label="Applied On"       value={fmtDate(candidate.created_at)} />
          <Row label="Added By"         value={candidate.added_by_name} />
          <Row label="Referred By"      value={candidate.referral_by_name || undefined} />

          {(candidate.interview_date || candidate.interviewer_name) && (
            <>
              <SectionTitle title="Interview" />
              <Row label="Date"        value={candidate.interview_date ? fmtDate(candidate.interview_date) : undefined} />
              <Row label="Interviewer" value={candidate.interviewer_name || undefined} />
              <Row label="Mode"        value={candidate.interview_mode || undefined} />
            </>
          )}

          {candidate.notes && (
            <>
              <SectionTitle title="Notes" />
              <p style={{ fontSize: ".85rem", color: "var(--on-bg)", lineHeight: 1.5 }}>{candidate.notes}</p>
            </>
          )}

          <div style={{ marginTop: "1.5rem", padding: ".75rem 1rem", borderRadius: 8, background: "var(--bg-low)", fontSize: ".82rem", color: "var(--on-variant)" }}>
            <i className="ti ti-info-circle" style={{ marginRight: 6 }} />
            The candidate has not yet filled in their detailed profile. Actions will be available once they submit.
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
