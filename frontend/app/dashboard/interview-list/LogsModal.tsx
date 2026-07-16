"use client";

import { useEffect, useState } from "react";
import { Candidate, CandidateLog, LogType, RECRUITMENT_API, fmtDateTime, initials } from "./_data";

const LOG_ICON: Record<LogType, string> = {
  success: "ti-check",
  error:   "ti-x",
  info:    "ti-info-circle",
  warn:    "ti-alert-triangle",
};

function Avatar({ name, size = 32 }: { name: string; size?: number }) {
  return (
    <div className="user-avatar" style={{ width: size, height: size, fontSize: size * 0.38, flexShrink: 0 }}>
      {initials(name)}
    </div>
  );
}

interface Props {
  candidate: Candidate;
  onClose:   () => void;
}

export function LogsModal({ candidate, onClose }: Props) {
  const [logs,    setLogs]    = useState<CandidateLog[]>(candidate.logs || []);
  const [loading, setLoading] = useState(!candidate.logs);

  useEffect(() => {
    if (candidate.logs) return;
    RECRUITMENT_API.detail(candidate.id)
      .then(r => setLogs(r.data.data.logs || []))
      .finally(() => setLoading(false));
  }, [candidate]);

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 480 }}>
        <div className="modal-header">
          <div className="modal-title">Activity Log — {candidate.name}</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          <div className="flex-row mb-16 pb-4 border-b border-[var(--outline-v)]">
            <Avatar name={candidate.name} size={40} />
            <div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>{candidate.name}</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
                {candidate.position_applied} • {candidate.email}
              </div>
            </div>
          </div>
          {loading ? (
            <div className="text-center py-6"><i className="ti ti-loader-2 spin text-2xl" /></div>
          ) : logs.length === 0 ? (
            <p className="text-center text-[var(--on-variant)]">No activity yet.</p>
          ) : (
            <div className="timeline">
              {logs.map(l => (
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
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
