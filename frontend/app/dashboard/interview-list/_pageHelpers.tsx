import { useState } from "react";
import { Candidate, CandidateStatus, RECRUITMENT_API, initials } from "./_data";

export const STATUS_META: Record<CandidateStatus, { label: string; cls: string; icon: string }> = {
  pending:              { label: "Pending",            cls: "badge-neutral", icon: "ti-clock" },
  screening:            { label: "Screening",          cls: "badge-info",    icon: "ti-eye" },
  interview_scheduled:  { label: "Interview Scheduled",cls: "badge-info",    icon: "ti-calendar" },
  interview_done:       { label: "Interview Done",     cls: "badge-warn",    icon: "ti-clipboard-check" },
  selected:             { label: "Selected",           cls: "badge-success", icon: "ti-check" },
  offer_sent:           { label: "Offer Sent",         cls: "badge-success", icon: "ti-send" },
  rejected:             { label: "Rejected",           cls: "badge-error",   icon: "ti-x" },
  converted:            { label: "Converted",          cls: "badge-neutral", icon: "ti-user-check" },
};

export function StatusBadge({ status }: { status: CandidateStatus }) {
  const meta = STATUS_META[status] ?? STATUS_META.pending;
  return (
    <span className={`badge ${meta.cls}`}>
      <i className={`ti ${meta.icon}`} /> {meta.label}
    </span>
  );
}

export function StatusDropdown({
  candidate,
  choices,
  onChanged,
  onMarkRequest,
}: {
  candidate: Candidate;
  choices: { value: CandidateStatus; label: string }[];
  onChanged: (updated: Candidate) => void;
  onMarkRequest: (candidate: Candidate, targetStatus: "selected" | "rejected") => void;
}) {
  const [updating, setUpdating] = useState(false);

  if (choices.length === 0) return null;

  // Ensure current status is always visible even if not in the choices list
  const hasCurrentStatus = choices.some(o => o.value === candidate.status);
  const options = hasCurrentStatus
    ? choices
    : [{ value: candidate.status, label: STATUS_META[candidate.status]?.label ?? candidate.status }, ...choices];

  async function handleChange(newStatus: CandidateStatus) {
    if (newStatus === candidate.status) return;
    // selected / rejected go through the modal (email template + preview)
    if (newStatus === "selected" || newStatus === "rejected") {
      onMarkRequest(candidate, newStatus);
      return;
    }
    setUpdating(true);
    try {
      const res = await RECRUITMENT_API.setStatus(candidate.id, { status: newStatus });
      onChanged(res.data?.data ?? { ...candidate, status: newStatus });
    } catch {
      // silently ignore — table will reflect current state on next load
    } finally {
      setUpdating(false);
    }
  }

  return (
    <select
      className="field-input field-select"
      style={{ fontSize: ".78rem", padding: "4px 28px 4px 8px", minWidth: 140, opacity: updating ? 0.6 : 1 }}
      value={candidate.status}
      disabled={updating}
      onChange={e => handleChange(e.target.value as CandidateStatus)}
      suppressHydrationWarning
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

export function Avatar({ name, size = 32 }: { name: string; size?: number }) {
  return (
    <div className="user-avatar" style={{ width: size, height: size, fontSize: size * 0.38, flexShrink: 0 }}>
      {initials(name)}
    </div>
  );
}
