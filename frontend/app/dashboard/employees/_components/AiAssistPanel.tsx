"use client";

// "AI Assist" — a real, deterministic filter helper for the Employee
// Directory. Deliberately not an LLM/AI call (no such service exists in
// this app) — it matches plain keywords against the real department/branch
// lists and status values the toolbar already filters on, and previews
// exactly what it detected before applying anything.

import { useMemo, useState } from "react";
import Modal from "@/components/Modal";
import { parseEmployeeQuery, type ParsedEmployeeStatus } from "@/lib/employeeQueryParser";

interface Props {
  departments: string[];
  branches: string[];
  onClose: () => void;
  onApply: (result: { status: ParsedEmployeeStatus | null; department: string | null; branch: string | null; search: string }) => void;
}

const EXAMPLES = [
  "onboarding employees in AI & ML",
  "active employees at Kondapur",
  "inactive employees in Platform Engineering",
];

export default function AiAssistPanel({ departments, branches, onClose, onApply }: Props) {
  const [query, setQuery] = useState("");

  const parsed = useMemo(
    () => (query.trim() ? parseEmployeeQuery(query, { departments, branches }) : null),
    [query, departments, branches],
  );

  function apply() {
    if (!parsed) return;
    onApply({ status: parsed.status, department: parsed.department, branch: parsed.branch, search: parsed.search });
    onClose();
  }

  return (
    <Modal
      title={<><i className="ti ti-sparkles" style={{ color: "var(--primary)" }} /> AI Assist</>}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={apply} disabled={!parsed}>
            Apply filters
          </button>
        </>
      }
    >
      <p style={{ fontSize: 12.5, color: "var(--on-variant)", marginBottom: 12 }}>
        Describe who you&apos;re looking for in plain words — this matches against real status, org unit and location
        filters (not an external AI service).
      </p>

      <textarea
        className="field-input"
        rows={2}
        autoFocus
        placeholder="e.g. onboarding employees in AI & ML"
        value={query}
        onChange={e => setQuery(e.target.value)}
      />

      <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 6 }}>
        {EXAMPLES.map(ex => (
          <button
            key={ex}
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setQuery(ex)}
          >
            {ex}
          </button>
        ))}
      </div>

      {parsed && (
        <div style={{ marginTop: 16, padding: "12px 14px", borderRadius: 10, background: "var(--bg-low)" }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", color: "var(--on-variant)", marginBottom: 6 }}>
            DETECTED
          </div>
          {parsed.matched.length === 0 ? (
            <div style={{ fontSize: 12.5, color: "var(--on-variant)" }}>
              Nothing matched a known status, org unit or location — Apply will search this text by name, ID or email instead.
            </div>
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: "var(--on-bg)" }}>
              {parsed.matched.map(m => <li key={m}>{m}</li>)}
            </ul>
          )}
        </div>
      )}
    </Modal>
  );
}
