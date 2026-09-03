"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import type { PayrollSettings, PayrollCycle } from "@/types/payroll";

interface BranchOption {
  id: string;
  branch_name: string;
  branch_code: string;
}

interface LockedBranch {
  id: string;
  name: string;
}

interface Props {
  settings: PayrollSettings | null;
  onNext: (cycleId: string) => void;
  onBack: () => void;
  initialMonth?: string;
  initialYear?: string;
  /** When set, branch is pre-filled and locked (HR user). */
  lockedBranch?: LockedBranch;
  /** When true, admin can pick any branch from a dropdown. */
  isAdmin?: boolean;
  /** Pre-selected branch for admin (e.g. when opening from branch overview). */
  initialBranchId?: string;
}

interface PagedBranches { results: BranchOption[]; count: number; }

const MONTHS = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];
const YEARS = ["2024","2025","2026","2027"];

function daysInMonth(month: number, year: number) { return new Date(year, month, 0).getDate(); }

function computeDates(month: string, year: string, settings: PayrollSettings | null) {
  const m = MONTHS.indexOf(month) + 1;
  const y = Number(year);
  const endMaxDay = daysInMonth(m, y);

  const startDayCfg = settings?.cycle_start_day ?? 1;
  const endDay       = Math.min(settings?.cycle_end_day ?? endMaxDay, endMaxDay);
  const payDay       = Math.min(settings?.pay_day       ?? 30, endMaxDay);

  let startMonth = m;
  let startYear  = y;
  if (startDayCfg > endDay) {
    startMonth = m - 1;
    if (startMonth === 0) {
      startMonth = 12;
      startYear  = y - 1;
    }
  }
  const startDay = Math.min(startDayCfg, daysInMonth(startMonth, startYear));

  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    cycle_start: `${startYear}-${pad(startMonth)}-${pad(startDay)}`,
    cycle_end:   `${y}-${pad(m)}-${pad(endDay)}`,
    pay_date:    `${y}-${pad(m)}-${pad(payDay)}`,
  };
}

export default function PayrollPeriodStep({
  settings,
  onNext,
  onBack,
  initialMonth,
  initialYear,
  lockedBranch,
  isAdmin,
  initialBranchId,
}: Props) {
  const today = new Date();
  const [month, setMonth]   = useState(initialMonth ?? MONTHS[today.getMonth()]);
  const [year,  setYear]    = useState(initialYear  ?? String(today.getFullYear()));
  const [notes, setNotes]   = useState("");
  const [branchId, setBranchId] = useState(initialBranchId ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError]   = useState<string | null>(null);

  const { data: branchesPage } = useFetch<PagedBranches>(
    isAdmin ? `${API.branches.list}?page_size=100` : null,
  );
  const branches = branchesPage?.results ?? [];

  const { cycle_start, cycle_end, pay_date } = computeDates(month, year, settings);

  async function createCycle() {
    if (isAdmin && !lockedBranch && !branchId) {
      setFormError("Please select a branch for this payroll run.");
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const payload: Record<string, string | undefined> = {
        cycle_start,
        cycle_end,
        pay_date,
        notes: notes.trim() || undefined,
      };

      if (lockedBranch?.id) {
        payload.branch_id = lockedBranch.id;
      } else if (isAdmin && branchId) {
        payload.branch_id = branchId;
      }

      const res = await clientApi.post<{ data: PayrollCycle }>(API.payroll.cycles, payload);
      onNext(res.data.data.id);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? "Failed to create payroll cycle. It may already exist for this period.";
      setFormError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  const selectedBranchName = lockedBranch?.name
    ?? branches.find(b => b.id === branchId)?.branch_name
    ?? "";

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar" /> Payroll Period Setup</div>
        <span className="badge badge-info">Step 1 of Wizard</span>
      </div>
      <div className="card-body">

        <div className="alert alert-info" style={{ marginBottom: 20 }}>
          <i className="ti ti-info-circle" />
          <span>Dates are auto-filled from your Payroll Run Settings. Adjust month/year to change them.</span>
        </div>

        {formError && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>
            <i className="ti ti-alert-circle" />
            <span>{formError}</span>
          </div>
        )}

        {/* Branch — locked for HR, selectable for admin */}
        {lockedBranch ? (
          <div className="field-group" style={{ marginBottom: 20 }}>
            <label className="field-label">Branch</label>
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 14px",
              background: "var(--bg-low)",
              borderRadius: "var(--radius)",
              border: "1px solid var(--outline-v)",
              fontWeight: 600,
              color: "var(--on-bg)",
            }}>
              <i className="ti ti-building" style={{ color: "var(--primary)", fontSize: 16 }} />
              {lockedBranch.name}
              <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--on-variant)", fontWeight: 400 }}>
                Your assigned branch
              </span>
            </div>
          </div>
        ) : isAdmin ? (
          <div className="field-group" style={{ marginBottom: 20 }}>
            <label className="field-label">Branch *</label>
            <select
              className="field-input field-select"
              value={branchId}
              onChange={e => setBranchId(e.target.value)}
            >
              <option value="">Select a branch…</option>
              {branches.map(b => (
                <option key={b.id} value={b.id}>{b.branch_name}</option>
              ))}
            </select>
          </div>
        ) : null}

        <div className="form-row cols-2">
          <div className="field-group">
            <label className="field-label">Payroll Month *</label>
            <select className="field-input field-select" value={month} onChange={e => setMonth(e.target.value)}>
              {MONTHS.map(m => <option key={m}>{m}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">Payroll Year *</label>
            <select className="field-input field-select" value={year} onChange={e => setYear(e.target.value)}>
              {YEARS.map(y => <option key={y}>{y}</option>)}
            </select>
          </div>
        </div>

        {/* Computed dates — read-only preview */}
        <div style={{
          background: "var(--bg-low)", borderRadius: "var(--radius)",
          padding: "16px 20px", marginBottom: 20, border: "1px solid var(--outline-v)",
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 12 }}>
            Computed Period Dates
            {selectedBranchName && (
              <span style={{ marginLeft: 8, color: "var(--primary)", textTransform: "none", fontWeight: 600 }}>
                — {selectedBranchName}
              </span>
            )}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
            {[
              { label: "Cycle Start", value: cycle_start, icon: "ti-calendar-event", color: "var(--info)"    },
              { label: "Cycle End",   value: cycle_end,   icon: "ti-calendar-event", color: "var(--warn)"    },
              { label: "Pay Date",    value: pay_date,    icon: "ti-credit-card",     color: "var(--success)" },
            ].map(f => (
              <div key={f.label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <i className={`ti ${f.icon}`} style={{ color: f.color, fontSize: 18 }} />
                <div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{f.label}</div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{f.value}</div>
                </div>
              </div>
            ))}
          </div>
          {!settings && (
            <div style={{ marginTop: 10, fontSize: 11, color: "var(--warn)" }}>
              <i className="ti ti-alert-triangle" style={{ marginRight: 4 }} />
              Payroll settings not configured — dates default to month boundaries.
              Go to Settings → Payroll Configuration to set custom days.
            </div>
          )}
        </div>

        <div className="field-group">
          <label className="field-label">Run Notes (optional)</label>
          <textarea
            className="field-input"
            placeholder="e.g. June 2026 regular payroll run"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            style={{ height: 70, resize: "none" }}
          />
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8, paddingTop: 20, borderTop: "1px solid var(--outline-v)" }}>
          <button className="btn btn-ghost" onClick={onBack} disabled={submitting}>
            <i className="ti ti-x" /> Cancel
          </button>
          <button className="btn btn-filled" onClick={createCycle} disabled={submitting}>
            {submitting
              ? <><i className="ti ti-loader-2 animate-spin" /> Creating…</>
              : <>Continue <i className="ti ti-arrow-right" /></>}
          </button>
        </div>
      </div>
    </div>
  );
}
