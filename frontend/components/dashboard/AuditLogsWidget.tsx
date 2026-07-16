"use client";

import { useState, useEffect, useCallback } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { AuditLogEntry, AuditLogsResponse } from "@/types/dashboard";

const PAGE_SIZE = 20;
const MODULES = ["All", "Employee", "Auth", "Leave", "Expense", "Payroll", "Settings", "Recruitment", "Attendance"];

const ACTION_CHIP: Record<string, { bg: string; color: string }> = {
  CREATE:  { bg: "rgba(27,138,107,0.12)",  color: "var(--success)" },
  UPDATE:  { bg: "rgba(181,101,29,0.12)",  color: "var(--warn)"    },
  DELETE:  { bg: "rgba(192,57,43,0.12)",   color: "var(--error)"   },
  LOGIN:   { bg: "rgba(14,124,134,0.12)",  color: "var(--info)"    },
  LOGOUT:  { bg: "rgba(14,124,134,0.08)",  color: "var(--info)"    },
  EXPORT:  { bg: "rgba(30,78,140,0.12)",   color: "var(--primary)" },
  APPROVE: { bg: "rgba(27,138,107,0.12)",  color: "var(--success)" },
  REJECT:  { bg: "rgba(192,57,43,0.12)",   color: "var(--error)"   },
};

function chipStyle(action: string): { bg: string; color: string } {
  return ACTION_CHIP[action.toUpperCase()] ?? { bg: "var(--bg-high)", color: "var(--on-variant)" };
}

function resolveField(log: AuditLogEntry, ...keys: (keyof AuditLogEntry)[]): string {
  for (const key of keys) {
    const val = log[key];
    if (val !== undefined && val !== null && val !== "") return String(val);
  }
  return "—";
}

function formatTimestamp(raw: string): string {
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: true });
}

export default function AuditLogsWidget() {
  const [moduleFilter, setModuleFilter] = useState("All");
  const [logs,         setLogs]         = useState<AuditLogEntry[]>([]);
  const [total,        setTotal]        = useState(0);
  const [offset,       setOffset]       = useState(0);
  const [loading,      setLoading]      = useState(true);
  const [loadingMore,  setLoadingMore]  = useState(false);
  const [error,        setError]        = useState<string | null>(null);

  const buildUrl = useCallback((mod: string, off: number) => {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(off) });
    if (mod !== "All") params.set("module", mod);
    return `${API.dashboard.auditLogs}?${params.toString()}`;
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setLogs([]);
    setOffset(0);
    clientApi
      .get<{ data: AuditLogsResponse }>(buildUrl(moduleFilter, 0))
      .then(res => {
        const payload: AuditLogsResponse = (res.data as unknown as { data: AuditLogsResponse }).data ?? (res.data as unknown as AuditLogsResponse);
        setLogs(payload.results ?? []);
        setTotal(payload.count ?? 0);
        setOffset(PAGE_SIZE);
      })
      .catch(() => setError("Failed to load audit logs."))
      .finally(() => setLoading(false));
  }, [moduleFilter, buildUrl]);

  function loadMore() {
    setLoadingMore(true);
    clientApi
      .get<{ data: AuditLogsResponse }>(buildUrl(moduleFilter, offset))
      .then(res => {
        const payload: AuditLogsResponse = (res.data as unknown as { data: AuditLogsResponse }).data ?? (res.data as unknown as AuditLogsResponse);
        setLogs(prev => [...prev, ...(payload.results ?? [])]);
        setOffset(prev => prev + PAGE_SIZE);
      })
      .catch(() => {})
      .finally(() => setLoadingMore(false));
  }

  const hasMore = logs.length < total;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-clipboard-list" /> Audit Logs</div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <select
            value={moduleFilter}
            onChange={e => setModuleFilter(e.target.value)}
            suppressHydrationWarning
            style={{
              fontSize: 11, padding: "4px 8px", borderRadius: 6,
              border: "1px solid var(--outline)", background: "var(--bg-base)",
              color: "var(--on-bg)", cursor: "pointer",
            }}
          >
            {MODULES.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <a href="/dashboard/settings/audit" className="btn btn-ghost btn-sm">
            View all <i className="ti ti-arrow-right" style={{ fontSize: 11, marginLeft: 3 }} />
          </a>
        </div>
      </div>

      {/* Column headers */}
      <div style={{ display: "grid", gridTemplateColumns: "82px 1fr 90px 80px", gap: 8, padding: "7px 16px", borderBottom: "1px solid var(--bg-high)", background: "var(--bg-low)" }}>
        {["Action", "Subject / Actor", "Module", "Time"].map(h => (
          <div key={h} style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase", color: "var(--on-variant)" }}>{h}</div>
        ))}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : error ? (
        <div style={{ padding: "20px", textAlign: "center", fontSize: 13, color: "var(--error)" }}>
          <i className="ti ti-alert-circle" style={{ marginRight: 6 }} />{error}
        </div>
      ) : logs.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>No logs found.</div>
      ) : (
        <>
          {logs.map(log => {
            const chip = chipStyle(log.action);
            const actor = resolveField(log, "actor", "actor_name");
            const ip = resolveField(log, "ip", "ip_address");
            const time = formatTimestamp(log.timestamp ?? log.created_at ?? "");
            return (
              <div key={String(log.id)} style={{ display: "grid", gridTemplateColumns: "82px 1fr 90px 80px", gap: 8, alignItems: "center", padding: "9px 16px", borderBottom: "1px solid var(--bg-high)" }}>
                <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4, background: chip.bg, color: chip.color, letterSpacing: "0.04em", display: "inline-block" }}>
                  {log.action.toUpperCase()}
                </span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, color: "var(--on-bg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{log.subject}</div>
                  <div style={{ fontSize: 10, color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 6, marginTop: 1 }}>
                    <i className="ti ti-user" style={{ fontSize: 9 }} />{actor}
                    {ip !== "—" && <><i className="ti ti-world" style={{ fontSize: 9, marginLeft: 2 }} />{ip}</>}
                  </div>
                </div>
                <span style={{ fontSize: 11, color: "var(--on-variant)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{log.module}</span>
                <div style={{ fontSize: 10, color: "var(--on-variant)", lineHeight: 1.3 }}>{time}</div>
              </div>
            );
          })}

          <div style={{ padding: "10px 16px", borderTop: "1px solid var(--bg-high)", background: "var(--bg-low)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: 11, color: "var(--on-variant)" }}>
              {logs.length} of {total} entries
            </span>
            {hasMore && (
              <button
                onClick={loadMore}
                disabled={loadingMore}
                suppressHydrationWarning
                style={{
                  fontSize: 12, color: "var(--primary)", fontWeight: 500, background: "none",
                  border: "none", cursor: loadingMore ? "not-allowed" : "pointer", opacity: loadingMore ? 0.6 : 1,
                  display: "flex", alignItems: "center", gap: 5,
                }}
              >
                {loadingMore ? <><i className="ti ti-loader-2 spin" style={{ fontSize: 12 }} /> Loading…</> : <>Load more <i className="ti ti-chevron-down" style={{ fontSize: 11 }} /></>}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
