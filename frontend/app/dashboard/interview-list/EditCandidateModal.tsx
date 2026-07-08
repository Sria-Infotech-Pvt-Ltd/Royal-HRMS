"use client";

import { useState } from "react";
import { normalizeExtraContext } from "@/lib/emailPreview";
import { Branch, Candidate, InterviewMode, MODE_LABELS, RECRUITMENT_API } from "./_data";

interface Props {
  candidate: Candidate;
  branches:  Branch[];
  onClose:   () => void;
  onSaved:   (updated: Candidate) => void;
}

const MODE_OPTIONS: InterviewMode[] = ["in_person", "video_call", "phone"];

export function EditCandidateModal({ candidate, branches, onClose, onSaved }: Props) {
  const [branch,         setBranch]         = useState<string>(candidate.branch ? String(candidate.branch) : "");
  const [interviewDate,  setInterviewDate]  = useState<string>(
    candidate.interview_date ? candidate.interview_date.slice(0, 16) : ""
  );
  const [interviewMode,  setInterviewMode]  = useState<InterviewMode>(candidate.interview_mode ?? "in_person");
  const [saving,         setSaving]         = useState(false);
  const [error,          setError]          = useState("");

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const formattedDate   = interviewDate ? interviewDate.slice(0, 10) : "";
      const isFirstSchedule = !!formattedDate && !candidate.interview_date;

      const res = await RECRUITMENT_API.update(candidate.id, {
        branch:         branch        ? Number(branch) : null,
        interview_date: formattedDate || null,
        interview_mode: interviewMode,
      });

      if (isFirstSchedule) {
        const parts     = candidate.name.trim().split(/\s+/);
        const firstName = parts[0] ?? candidate.name;
        const lastName  = parts.length > 1 ? parts[parts.length - 1] : "";
        const extraContext = normalizeExtraContext({
          candidate_name:         candidate.name,
          full_name:              candidate.name,
          first_name:             firstName,
          last_name:              lastName,
          email:                  candidate.email,
          position_applied:       candidate.position_applied,
          position:               candidate.position_applied,
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

      onSaved(res.data?.data ?? { ...candidate, branch: branch ? Number(branch) : null, interview_date: formattedDate || null, interview_mode: interviewMode });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to save changes.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.6)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div style={{ background: "var(--surface, #fff)", borderRadius: 16, width: "100%", maxWidth: 480, boxShadow: "0 20px 50px rgba(0,0,0,0.22)" }}>

        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", padding: "18px 20px", borderBottom: "1px solid var(--outline-v)" }}>
          <div>
            <p style={{ fontWeight: 700, fontSize: 15, color: "var(--on-bg)", margin: 0 }}>Edit Interview Details</p>
            <p style={{ fontSize: 12, color: "var(--on-variant)", margin: "2px 0 0" }}>{candidate.name} · {candidate.position_applied}</p>
          </div>
          <button
            style={{ width: 30, height: 30, borderRadius: 8, border: "none", background: "var(--bg)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--on-variant)" }}
            onClick={onClose} suppressHydrationWarning>
            <i className="ti ti-x" />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "20px" }}>
          {error && (
            <div className="alert alert-error" style={{ marginBottom: 16 }}>
              <i className="ti ti-alert-circle" /><div>{error}</div>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field-group">
              <label className="field-label">Branch <span style={{ color: "var(--error)" }}>*</span></label>
              <select className="field-input field-select" value={branch}
                onChange={e => setBranch(e.target.value)} suppressHydrationWarning>
                <option value="">Select branch</option>
                {branches.map(b => (
                  <option key={b.id} value={b.id}>{b.branch_name} ({b.branch_code})</option>
                ))}
              </select>
            </div>

            <div className="field-group">
              <label className="field-label">Interview Date</label>
              <input type="date" className="field-input"
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

          <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
            <button className="btn btn-filled" onClick={handleSave} disabled={saving || !branch} suppressHydrationWarning>
              {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : <><i className="ti ti-device-floppy" /> Save Changes</>}
            </button>
            <button className="btn btn-ghost" onClick={onClose} suppressHydrationWarning>
              Cancel
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
