"use client";

// Settings → Leave Policy: Maximum Late Arrivals Per Month (company-wide,
// tracking only — it never adds LOP), and the employees over the limit in
// a chosen month. Editing follows the Leave Policy permission (server-enforced).

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import ToggleSwitch from "@/components/ToggleSwitch";
import {
  LATE_LIMIT_BADGE, LATE_LIMIT_MAX, maximumError, type LateLimitEmployee, type LateLimitSetting,
} from "@/lib/lateLimit";

function thisMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function LateArrivalLimitCard() {
  const { showToast } = useToast();
  // Who's over the limit: HR (attendance.edit) or Leave Policy admins — the server also scopes it.
  const canSeeEmployees = usePermission("attendance.edit");
  const { data, loading, refetch } = useFetch<LateLimitSetting>(API.attendance.lateArrivalLimit);
  const [enabled, setEnabled] = useState(true);
  const [maximum, setMaximum] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [month, setMonth] = useState(thisMonth());
  const [includeReached, setIncludeReached] = useState(false);

  useEffect(() => {
    if (data) { setEnabled(data.enabled); setMaximum(String(data.maximum)); }
  }, [data]);

  const { data: over, loading: overLoading, refetch: refetchOver } = useFetch<{ results: LateLimitEmployee[]; enabled: boolean; maximum: number }>(
    canSeeEmployees || data?.can_edit
      ? `${API.attendance.lateArrivalLimitEmployees}?month=${month}${includeReached ? "&include_reached=true" : ""}`
      : null);

  const canEdit = !!data?.can_edit;
  const fieldErr = enabled ? maximumError(maximum) : (maximum.trim() ? maximumError(maximum) : null);
  const dirty = !!data && (data.enabled !== enabled || String(data.maximum) !== maximum.trim());

  async function save() {
    if (fieldErr) { setErr(fieldErr); return; }
    setSaving(true);
    setErr(null);
    try {
      await clientApi.put(API.attendance.lateArrivalLimit, { enabled, maximum: Number(maximum.trim() || data?.maximum || 5) });
      showToast("Late arrival limit saved.", "success");
      refetch();
      refetchOver();
    } catch (e) {
      setErr((e as { message?: string })?.message ?? "Could not save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card mb-16">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-clock-exclamation" /> Maximum Late Arrivals Per Month</div>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 13 }}>
        {loading && !data ? <div>Loading…</div> : (
          <>
            <div style={{ color: "var(--on-variant)" }}>
              Company-wide tracking limit, counted per calendar month and reset on the 1st. Late (Excused) days are not
              counted. <strong>It does not add LOP</strong> — late-mark deductions stay as set in Settings → Attendance Rules.
            </div>
            {data && !data.configured && (
              <div className="alert alert-warn">Save Settings → Attendance Rules once before changing this limit. Until then the default applies.</div>
            )}
            <table className="data-table" style={{ maxWidth: 560 }}>
              <thead><tr><th>Setting</th><th>Configuration</th></tr></thead>
              <tbody>
                <tr>
                  <td>Maximum Late Arrivals Per Month</td>
                  <td><ToggleSwitch checked={enabled} onChange={setEnabled} disabled={!canEdit || saving}
                    label={enabled ? "Enabled" : "Disabled"} /></td>
                </tr>
                <tr>
                  <td>Maximum Allowed Late Arrivals</td>
                  <td>
                    <input className="field-input" type="number" min={1} max={LATE_LIMIT_MAX} step={1} inputMode="numeric"
                      style={{ maxWidth: 110 }} value={maximum} disabled={!canEdit || saving || !enabled}
                      onChange={e => { setMaximum(e.target.value); setErr(null); }} />
                    {fieldErr && canEdit && <div style={{ color: "var(--error)", fontSize: 12, marginTop: 4 }}>{fieldErr}</div>}
                  </td>
                </tr>
              </tbody>
            </table>
            {err && <div className="alert alert-error">{err}</div>}
            {canEdit ? (
              <div>
                <button className="btn btn-filled btn-sm" disabled={!dirty || saving || !!fieldErr || !data?.configured} onClick={save}>
                  {saving ? "Saving…" : "Save"}
                </button>
              </div>
            ) : (
              <div style={{ fontSize: 12, color: "var(--on-variant)" }}>Read only — only Leave Policy administrators can change this.</div>
            )}

            {(canSeeEmployees || canEdit) && (
              <div style={{ borderTop: "1px solid var(--outline-v)", paddingTop: 12 }}>
                <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
                  <strong>Employees over the limit</strong>
                  <input className="field-input" type="month" value={month} style={{ maxWidth: 170 }}
                    onChange={e => e.target.value && setMonth(e.target.value)} />
                  <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input type="checkbox" checked={includeReached} onChange={e => setIncludeReached(e.target.checked)} /> Include “Limit reached”
                  </label>
                </div>
                {over && !over.enabled ? (
                  <div style={{ color: "var(--on-variant)" }}>The limit is disabled — nothing is tracked.</div>
                ) : overLoading ? <div>Loading…</div> : (over?.results ?? []).length === 0 ? (
                  <div style={{ color: "var(--on-variant)" }}>No employees {includeReached ? "at or over" : "over"} the limit of {over?.maximum ?? data?.maximum} in this month.</div>
                ) : (
                  <div className="table-wrap">
                    <table className="data-table" style={{ width: "100%" }}>
                      <thead><tr><th>Employee</th><th>Branch</th><th>Department</th><th style={{ textAlign: "right" }}>Late arrivals</th><th>Status</th></tr></thead>
                      <tbody>
                        {(over?.results ?? []).map(r => (
                          <tr key={r.employee}>
                            <td><strong>{r.name}</strong> <span style={{ color: "var(--on-variant)" }}>{r.employee_code}</span></td>
                            <td>{r.branch || "—"}</td>
                            <td>{r.department || "—"}</td>
                            <td style={{ textAlign: "right" }}>{r.late_arrivals} / {over?.maximum}</td>
                            <td><span className={LATE_LIMIT_BADGE[r.status]}>{r.status_label}{r.over_by ? ` (+${r.over_by})` : ""}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
