"use client";

import { useState } from "react";

interface Props { onNext: () => void; onBack: () => void; }

type IssueSeverity = "error" | "warn" | "info";
interface Issue {
  id:        string;
  type:      string;
  employees: string[];
  severity:  IssueSeverity;
  message:   string;
  status:    "open" | "fixed" | "ignored";
}

const INIT_ISSUES: Issue[] = [
  { id: "1", type: "Missing Attendance",      employees: ["Priya Sharma"],                   severity: "error", message: "Attendance not marked for 2 days (Jun 10, Jun 15). LOP will be calculated automatically.", status: "open" },
  { id: "2", type: "Missing Salary Structure", employees: ["Kavita Rao"],                     severity: "error", message: "No salary structure assigned. Employee will be excluded from this payroll run.",             status: "open" },
  { id: "3", type: "Missing Bank Details",     employees: ["Rajesh Kumar", "Ananya Menon"],   severity: "error", message: "Bank account details not provided. Salary cannot be disbursed via NEFT.",                   status: "open" },
  { id: "4", type: "Missing PF Number",        employees: ["Suresh Kumar"],                   severity: "warn",  message: "PF number not registered. PF deduction may not be mapped to the correct account.",           status: "open" },
  { id: "5", type: "Missing ESI Number",       employees: ["Arjun Mehta"],                   severity: "warn",  message: "ESI not applicable — employee salary exceeds ₹21,000 threshold.",                            status: "open" },
  { id: "6", type: "TDS Mismatch",             employees: ["Rahul Singh"],                    severity: "info",  message: "Declared investments differ from projected TDS. Recommend re-verification before filing.",     status: "open" },
];

const SEV_CONFIG: Record<IssueSeverity, { icon: string; badge: string; label: string }> = {
  error: { icon: "ti-alert-circle",    badge: "badge badge-error",   label: "Error"   },
  warn:  { icon: "ti-alert-triangle",  badge: "badge badge-warn",    label: "Warning" },
  info:  { icon: "ti-info-circle",     badge: "badge badge-info",    label: "Info"    },
};

export default function ValidationStep({ onNext, onBack }: Props) {
  const [issues, setIssues] = useState<Issue[]>(INIT_ISSUES);

  function fix(id: string)    { setIssues(p => p.map(i => i.id === id ? { ...i, status: "fixed" }   : i)); }
  function ignore(id: string) { setIssues(p => p.map(i => i.id === id ? { ...i, status: "ignored" } : i)); }

  const errors   = issues.filter(i => i.severity === "error" && i.status === "open").length;
  const warnings = issues.filter(i => i.severity === "warn"  && i.status === "open").length;
  const open     = issues.filter(i => i.status === "open").length;
  const canContinue = errors === 0;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-shield-check" /> Validation</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {errors > 0   && <span className="badge badge-error"><i className="ti ti-alert-circle" /> {errors} Errors</span>}
          {warnings > 0 && <span className="badge badge-warn"><i className="ti ti-alert-triangle" /> {warnings} Warnings</span>}
          {open === 0   && <span className="badge badge-success"><i className="ti ti-check" /> All Clear</span>}
          <span className="badge badge-info">Step 8 of 11</span>
        </div>
      </div>
      <div className="card-body">

        {errors > 0 && (
          <div className="alert alert-error" style={{ marginBottom: 20 }}>
            <i className="ti ti-alert-circle" />
            <span>There are <strong>{errors} critical error(s)</strong> that must be resolved or ignored before you can continue.</span>
          </div>
        )}
        {canContinue && open > 0 && (
          <div className="alert alert-warn" style={{ marginBottom: 20 }}>
            <i className="ti ti-alert-triangle" />
            <span>No critical errors. You may continue with {open} unresolved warning(s).</span>
          </div>
        )}
        {open === 0 && (
          <div className="alert alert-success" style={{ marginBottom: 20 }}>
            <i className="ti ti-circle-check" />
            <span>All validation checks passed. Ready to proceed to approval.</span>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {issues.map(issue => {
            const cfg = SEV_CONFIG[issue.severity];
            const isDone = issue.status !== "open";
            return (
              <div
                key={issue.id}
                style={{
                  border: `1.5px solid ${isDone ? "var(--outline-v)" : issue.severity === "error" ? "#ffb3ae" : issue.severity === "warn" ? "#fde68a" : "#b3d1f5"}`,
                  borderRadius: "var(--radius)",
                  padding: "14px 16px",
                  background: isDone ? "var(--bg-low)" : "transparent",
                  opacity: isDone ? 0.6 : 1,
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 14,
                }}
              >
                <i className={`ti ${cfg.icon}`} style={{ fontSize: 20, color: isDone ? "var(--outline)" : issue.severity === "error" ? "var(--error)" : issue.severity === "warn" ? "var(--warn)" : "var(--info)", marginTop: 1, flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{issue.type}</span>
                    <span className={cfg.badge}>{cfg.label}</span>
                    {isDone && <span className={`badge ${issue.status === "fixed" ? "badge-success" : "badge-neutral"}`}>{issue.status === "fixed" ? "Fixed" : "Ignored"}</span>}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 8 }}>{issue.message}</div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {issue.employees.map(name => (
                      <span key={name} className="badge badge-neutral">{name}</span>
                    ))}
                  </div>
                </div>
                {!isDone && (
                  <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                    <button className="btn btn-success btn-sm" onClick={() => fix(issue.id)}>
                      <i className="ti ti-tool" /> Fix
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => ignore(issue.id)}>
                      <i className="ti ti-eye-off" /> Ignore
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
        <button className="btn btn-filled" onClick={onNext} disabled={!canContinue} style={{ opacity: canContinue ? 1 : 0.5 }}>
          Continue <i className="ti ti-arrow-right" />
        </button>
      </div>
    </div>
  );
}
