"use client";

import { useState } from "react";
import { normalizeExtraContext } from "@/lib/emailPreview";
import { NAME_RE, POSITION_RE, sanitizeName, sanitizePosition, todayDateString } from "@/lib/candidateValidation";
import { Branch, Candidate, InterviewMode, MODE_LABELS, RECRUITMENT_API } from "./_data";

interface Props {
  candidate: Candidate;
  branches:  Branch[];
  onClose:   () => void;
  onSaved:   (updated: Candidate) => void;
}

const MODE_OPTIONS: InterviewMode[] = ["in_person", "video_call", "phone"];
const todayStr = todayDateString();

export function EditCandidateModal({ candidate, branches, onClose, onSaved }: Props) {
  const [name,           setName]           = useState<string>(candidate.name);
  const [positionApplied,setPositionApplied]= useState<string>(candidate.position_applied);
  const [branch,         setBranch]         = useState<string>(candidate.branch ? String(candidate.branch) : "");
  const [interviewDate,  setInterviewDate]  = useState<string>(
    candidate.interview_date ? candidate.interview_date.slice(0, 16) : ""
  );
  const [interviewMode,  setInterviewMode]  = useState<InterviewMode>(candidate.interview_mode ?? "in_person");
  const [saving,         setSaving]         = useState(false);
  const [error,          setError]          = useState("");

  async function handleSave() {
    const trimmedName = name.trim();
    const trimmedPosition = positionApplied.trim();
    if (!trimmedName || !trimmedPosition) {
      setError("Name and position are required.");
      return;
    }
    if (!NAME_RE.test(trimmedName)) {
      setError("Full name can only contain letters, spaces, apostrophes, hyphens, and periods — no numbers or special characters.");
      return;
    }
    if (!POSITION_RE.test(trimmedPosition)) {
      setError("Position applied can only contain letters, spaces, and & / . - — no numbers or other special characters.");
      return;
    }
    if (!branch) {
      setError("Please select a branch.");
      return;
    }
    const formattedDate     = interviewDate ? interviewDate.slice(0, 10) : "";
    const originalDate      = candidate.interview_date ? candidate.interview_date.slice(0, 10) : "";
    if (formattedDate && formattedDate < todayStr && formattedDate !== originalDate) {
      setError("Interview date cannot be in the past.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const isFirstSchedule = !!formattedDate && !candidate.interview_date;

      const res = await RECRUITMENT_API.update(candidate.id, {
        name:             name.trim(),
        position_applied: positionApplied.trim(),
        branch:           branch ? Number(branch) : null,
        interview_date:   formattedDate || null,
        interview_mode:   interviewMode,
      });

      if (isFirstSchedule) {
        const parts     = name.trim().split(/\s+/);
        const firstName = parts[0] ?? name;
        const lastName  = parts.length > 1 ? parts[parts.length - 1] : "";
        const extraContext = normalizeExtraContext({
          candidate_name:         name,
          full_name:              name,
          first_name:             firstName,
          last_name:              lastName,
          email:                  candidate.email,
          position_applied:       positionApplied,
          position:               positionApplied,
          branch_name:            candidate.branch_name ?? "",
          interview_date:         formattedDate,
          interview_mode:         interviewMode,
          interview_mode_display: MODE_LABELS[interviewMode] ?? interviewMode,
        });
        await RECRUITMENT_API.sendEmail(candidate.id, {
          template_name: "interview_scheduled_candidate",
          extra_context: extraContext,
        });
      }

      onSaved(res.data?.data ?? {
        ...candidate,
        name:             name.trim(),
        position_applied: positionApplied.trim(),
        branch:           branch ? Number(branch) : null,
        interview_date:   formattedDate || null,
        interview_mode:   interviewMode,
      });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to save changes.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 520 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="modal-title">Edit Interview Details</div>
            <p style={{ fontSize: 12, color: "var(--on-variant)", margin: "2px 0 0" }}>{candidate.email}</p>
          </div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body">
          {error && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" /><div>{error}</div>
            </div>
          )}

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Full Name *</label>
              <input className="field-input" value={name} onChange={e => setName(sanitizeName(e.target.value))} suppressHydrationWarning />
            </div>
            <div className="field-group">
              <label className="field-label">Position Applied *</label>
              <input className="field-input" value={positionApplied} onChange={e => setPositionApplied(sanitizePosition(e.target.value))} suppressHydrationWarning />
            </div>
          </div>

          <div className="field-group mb-16">
            <label className="field-label">Branch <span style={{ color: "var(--error)" }}>*</span></label>
            <select className="field-input field-select" value={branch}
              onChange={e => setBranch(e.target.value)} suppressHydrationWarning>
              <option value="">Select branch</option>
              {branches.map(b => (
                <option key={b.id} value={b.id}>{b.branch_name} ({b.branch_code})</option>
              ))}
            </select>
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Interview Date</label>
              <input type="date" className="field-input"
                min={todayStr}
                value={interviewDate.slice(0, 10)}
                onChange={e => setInterviewDate(e.target.value)}
                suppressHydrationWarning />
              {interviewDate && !candidate.interview_date && (
                <p style={{ fontSize: 11, color: "var(--info, #0284c7)", marginTop: 5, display: "flex", alignItems: "center", gap: 5 }}>
                  <i className="ti ti-mail" /> An interview invitation email will be sent to the candidate.
                </p>
              )}
            </div>

            <div className="field-group">
              <label className="field-label">Interview Mode</label>
              <select className="field-input field-select" value={interviewMode}
                onChange={e => setInterviewMode(e.target.value as InterviewMode)} suppressHydrationWarning>
                {MODE_OPTIONS.map(m => (
                  <option key={m} value={m}>{MODE_LABELS[m]}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} suppressHydrationWarning>
            Cancel
          </button>
          <button className="btn btn-filled" onClick={handleSave} disabled={saving || !branch || !name.trim() || !positionApplied.trim()} suppressHydrationWarning>
            {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : <><i className="ti ti-device-floppy" /> Save Changes</>}
          </button>
        </div>
      </div>
    </div>
  );
}
