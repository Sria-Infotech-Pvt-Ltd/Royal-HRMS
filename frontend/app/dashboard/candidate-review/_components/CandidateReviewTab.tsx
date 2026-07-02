"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Candidate,
  CandidateDocument,
  CandidateLog,
  LogType,
  RECRUITMENT_API,
  fmtDateTime,
  initials,
} from "../../interview-list/_data";
import { HRDecisionModal } from "../HRDecisionModal";
import DocPreviewModal from "@/components/DocPreviewModal";

// ── Small helpers ─────────────────────────────────────────────────────────────

function Avatar({ name, size = 32 }: { name: string; size?: number }) {
  return (
    <div className="user-avatar" style={{ width: size, height: size, fontSize: size * 0.38, flexShrink: 0 }}>
      {initials(name)}
    </div>
  );
}

const LOG_ICON: Record<LogType, string> = {
  success: "ti-check",
  error:   "ti-x",
  info:    "ti-info-circle",
  warn:    "ti-alert-triangle",
};

// ── Candidate Accordion Item ──────────────────────────────────────────────────

interface AccordionItemProps {
  candidate:  Candidate;
  onDecision: (c: Candidate, d: "approve" | "reject") => void;
}

function CandidateAccordionItem({ candidate: initial, onDecision }: AccordionItemProps) {
  const [open,       setOpen]       = useState(false);
  const [previewDoc, setPreviewDoc] = useState<CandidateDocument | null>(null);

  const c = initial;

  // ── Stage flags ───────────────────────────────────────────────────────────
  const isPendingReview = c.details_filled && !c.hr_approved;
  const isApproved      = c.hr_approved;

  // ── Badge ─────────────────────────────────────────────────────────────────
  let badge: React.ReactNode;
  if      (isApproved)      badge = <span className="badge badge-success">HR Approved</span>;
  else if (isPendingReview) badge = <span className="badge badge-warn">Review Pending</span>;
  else                      badge = <span className="badge badge-info">Awaiting Onboarding</span>;

  const docs = c.documents ?? [];

  return (
    <>
      {previewDoc && (
        <DocPreviewModal
          name={previewDoc.document_type_display}
          fileName={previewDoc.file_name}
          fileUrl={previewDoc.file_url}
          fileSize={previewDoc.file_size}
          onClose={() => setPreviewDoc(null)}
        />
      )}

      <div className="accordion-item mb-12">
        <div className={`accordion-header ${open ? "open" : ""}`} onClick={() => setOpen(o => !o)}>
          <Avatar name={c.name} size={32} />
          <div className="flex-1">
            <div className="text-sm font-medium">{c.name}</div>
            <div className="text-xs text-[var(--on-variant)]">{c.position_applied} · {c.branch_name}</div>
          </div>
          {badge}
          <i className={`ti ti-chevron-down accordion-toggle ${open ? "rotated" : ""}`} />
        </div>

        {open && (
          <div className="accordion-body">

            {/* ── Awaiting onboarding ── */}
            {!isPendingReview && !isApproved && (
              <div className="alert alert-info">
                <i className="ti ti-clock" />
                <div>Waiting for the candidate to complete and submit the onboarding form.</div>
              </div>
            )}

            {/* ── Onboarding submitted — review ── */}
            {isPendingReview && (
              <>
                <div className="grid-2 mb-16">
                  <div>
                    <div className="settings-card-title mb-8">Personal Details</div>
                    <div className="text-[13px] leading-loose text-[var(--on-variant)]">
                      <strong className="text-[var(--on-bg)]">Full Name:</strong> {c.name}<br />
                      <strong className="text-[var(--on-bg)]">Email:</strong> {c.email}<br />
                      <strong className="text-[var(--on-bg)]">Phone:</strong> {c.phone || "—"}<br />
                      <strong className="text-[var(--on-bg)]">Position:</strong> {c.position_applied}
                    </div>
                  </div>
                  <div>
                    <div className="settings-card-title mb-8">Uploaded Documents</div>
                    {docs.length === 0 ? (
                      <p className="text-[13px] text-[var(--on-variant)]">No documents uploaded yet.</p>
                    ) : (
                      docs.map(d => (
                        <div key={d.id} className="flex items-center gap-2 py-1.5 border-b border-[var(--outline-v)]">
                          <i className="ti ti-file-check text-[var(--success)]" />
                          <span className="text-[13px]">{d.document_type_display}</span>
                          <button
                            className="btn btn-ghost btn-sm"
                            style={{ marginLeft: "auto" }}
                            onClick={() => setPreviewDoc(d)}
                            suppressHydrationWarning
                          >
                            <i className="ti ti-eye" />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
                <div className="flex items-end flex-wrap gap-3">
                  <button className="btn btn-danger" onClick={() => onDecision(c, "reject")} suppressHydrationWarning>
                    <i className="ti ti-refresh" /> Request Revision
                  </button>
                  <button className="btn btn-success" onClick={() => onDecision(c, "approve")} suppressHydrationWarning>
                    <i className="ti ti-check" /> Approve & Onboard
                  </button>
                </div>
              </>
            )}

            {/* ── Approved — assessment invited ── */}
            {isApproved && (
              <div className="alert alert-success">
                <i className="ti ti-check" />
                <div>
                  <strong>Onboarding approved.</strong> Assessment invitation sent to{" "}
                  <strong>{c.email}</strong>. The candidate has been asked to attend the assessment.
                </div>
              </div>
            )}

            {/* ── Activity log ── */}
            {c.logs && c.logs.length > 0 && (
              <div className="mt-16">
                <div className="settings-card-title flex items-center gap-1 mb-8">
                  <i className="ti ti-history" /> Activity Log
                </div>
                <div className="timeline">
                  {c.logs.map((l: CandidateLog) => (
                    <div key={l.id} className="tl-item">
                      <div className={`tl-dot tl-${l.log_type}`}><i className={`ti ${LOG_ICON[l.log_type]}`} /></div>
                      <div className="tl-body">
                        <div className="tl-title">{l.title}</div>
                        {l.description && <div className="tl-desc">{l.description}</div>}
                        <div className="tl-time">{fmtDateTime(l.created_at)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ── Page-level tab ────────────────────────────────────────────────────────────

export default function CandidateReviewTab() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState("");
  const [modal,      setModal]      = useState<{ candidate: Candidate; decision: "approve" | "reject" } | null>(null);

  const fetchReview = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await RECRUITMENT_API.reviewList();
      const raw = res.data?.data;
      setCandidates(Array.isArray(raw?.results) ? raw.results : []);
    } catch {
      setError("Failed to load candidates for review.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchReview(); }, [fetchReview]);

  function handleDecisionDone(updated: Candidate) {
    setCandidates(prev => prev.map(c => c.id === updated.id ? { ...c, ...updated } : c));
    setModal(null);
  }

  const awaitingOnboarding = candidates.filter(c => !c.details_filled && !c.hr_approved).length;
  const pendingReview      = candidates.filter(c => c.details_filled && !c.hr_approved).length;
  const approved           = candidates.filter(c => c.hr_approved).length;

  return (
    <>
      <div className="stats-grid" style={{ marginBottom: 20 }}>
        {[
          { label: "Awaiting Onboarding", value: awaitingOnboarding, icon: "ti-clock",      iconCls: "si-info"    },
          { label: "Pending Review",      value: pendingReview,      icon: "ti-eye",        iconCls: "si-warn"    },
          { label: "Approved",            value: approved,           icon: "ti-user-check", iconCls: "si-success" },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div className={`stat-icon ${s.iconCls}`}><i className={`ti ${s.icon}`} /></div>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value">{s.value}</div>
          </div>
        ))}
      </div>

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{error}</div></div>}

      {loading ? (
        <div className="text-center py-16"><i className="ti ti-loader-2 spin text-3xl" /></div>
      ) : candidates.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-user-check" />
          <h3>No candidates in pipeline</h3>
          <p>Candidates marked as selected will appear here.</p>
        </div>
      ) : (
        candidates.map(c => (
          <CandidateAccordionItem
            key={c.id}
            candidate={c}
            onDecision={(cand, dec) => setModal({ candidate: cand, decision: dec })}
          />
        ))
      )}

      {modal && (
        <HRDecisionModal
          candidate={modal.candidate}
          decision={modal.decision}
          onClose={() => setModal(null)}
          onDone={handleDecisionDone}
        />
      )}
    </>
  );
}
