"use client";

import { useCallback, useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";

// ─── Types ────────────────────────────────────────────────────────────────────

type EmailLogRow = {
  id:                     string;
  recipient_email:        string;
  subject:                string;
  status:                 "sent" | "failed";
  module:                 string;
  template_name:          string;
  triggered_by_name:      string;
  smtp_settings_name:     string;
  is_resend:              boolean;
  had_attachments:        boolean;
  has_sensitive_context:  boolean;
  error_message:          string;
  created_at:             string;
};

type PageData = {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     EmailLogRow[];
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

// Keep in sync with backend's EmailLog module values (apps.accounts.utils
// send_template_email call sites) — same reconciliation risk the Audit Log
// page's own hardcoded MODULES list already carries.
const MODULES = [
  { value: "hrms",         label: "HRMS"         },
  { value: "recruitment",  label: "Recruitment"  },
  { value: "accounts",     label: "Accounts"     },
  { value: "attendance",   label: "Attendance"   },
  { value: "payroll",      label: "Payroll"      },
  { value: "notifications",label: "Notifications"},
  { value: "assessments",  label: "Assessments"  },
];

function moduleClass(module: string): string {
  switch (module) {
    case "hrms":          return "badge-primary";
    case "recruitment":   return "badge-info";
    case "accounts":      return "badge-warn";
    case "attendance":    return "badge-success";
    case "payroll":       return "badge-error";
    case "notifications": return "badge-neutral";
    case "assessments":   return "badge-primary";
    default:              return "badge-neutral";
  }
}

function isoToday(): string {
  return new Date().toISOString().split("T")[0];
}

function iso30DaysAgo(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().split("T")[0];
}

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function EmailLogsPage() {
  const canResend = usePermission("email_logs.resend");

  const [pageData, setPageData] = useState<PageData | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  const [status,   setStatus]   = useState("");
  const [module,   setModule]   = useState("");
  const [search,   setSearch]   = useState("");
  const [dateFrom, setDateFrom] = useState(iso30DaysAgo());
  const [dateTo,   setDateTo]   = useState(isoToday());
  const [page,     setPage]     = useState(1);

  const [resendingId, setResendingId] = useState<string | null>(null);
  const [resendMsg,   setResendMsg]   = useState<string | null>(null);
  const [resendErr,   setResendErr]   = useState<string | null>(null);

  const fetchLogs = useCallback(async (pg: number) => {
    setLoading(true);
    setApiError(null);
    try {
      const params: Record<string, string> = { page: String(pg), page_size: "20" };
      if (status)   params.status    = status;
      if (module)   params.module    = module;
      if (search)   params.search    = search;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo)   params.date_to   = dateTo;

      const res = await clientApi.get(API.settings.emailLogs, { params });
      setPageData(res.data?.data ?? null);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setApiError(e.message ?? "Failed to load email logs.");
    } finally {
      setLoading(false);
    }
  }, [status, module, search, dateFrom, dateTo]);

  useEffect(() => {
    setPage(1);
    fetchLogs(1);
  }, [status, module, dateFrom, dateTo, fetchLogs]);

  useEffect(() => {
    fetchLogs(page);
  }, [page, fetchLogs]);

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    fetchLogs(1);
  }

  async function handleResend(row: EmailLogRow) {
    setResendingId(row.id);
    setResendMsg(null);
    setResendErr(null);
    try {
      const res = await clientApi.post(API.settings.emailLogResend(row.id));
      const data = res.data?.data;
      const warning = data?.warning ? ` ${data.warning}` : "";
      setResendMsg((res.data?.message ?? `Resent to ${row.recipient_email}.`) + warning);
      fetchLogs(page);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to resend email.";
      setResendErr(msg);
    } finally {
      setResendingId(null);
    }
  }

  const hasActiveFilters = status || module || search || dateFrom !== iso30DaysAgo() || dateTo !== isoToday();

  function clearFilters() {
    setStatus("");
    setModule("");
    setSearch("");
    setDateFrom(iso30DaysAgo());
    setDateTo(isoToday());
    setPage(1);
  }

  const rows = pageData?.results ?? [];

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Email Logs</div>
          <div className="page-sub">System-wide email delivery history and status</div>
        </div>
      </div>

      {/* ── Filters ─────────────────────────────────────────────────────── */}
      {/* Explicit minWidth:0/flexWrap/maxWidth here rather than relying only
          on globals.css's .filter-bar shrink rules — those only kick in
          under the 768px mobile breakpoint, leaving a gap at ordinary laptop
          widths where this row (one more field than the pattern it's based
          on) could force the whole page to scroll horizontally instead of
          wrapping onto a second line. */}
      <form onSubmit={handleSearchSubmit} className="filter-bar" style={{ maxWidth: "100%", flexWrap: "wrap", rowGap: 10 }}>
        <div className="search-bar" style={{ flex: "1 1 180px", minWidth: 0 }}>
          <i className="ti ti-search" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by recipient or subject…"
            suppressHydrationWarning
          />
        </div>

        <select className="field-input field-select" style={{ width: 120, flexShrink: 0 }} value={status} onChange={e => setStatus(e.target.value)} suppressHydrationWarning>
          <option value="">All statuses</option>
          <option value="sent">Sent</option>
          <option value="failed">Failed</option>
        </select>

        <select className="field-input field-select" style={{ width: 150, flexShrink: 0 }} value={module} onChange={e => setModule(e.target.value)} suppressHydrationWarning>
          <option value="">All modules</option>
          {MODULES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>

        <input
          className="field-input" type="date" style={{ width: 140, flexShrink: 0 }}
          value={dateFrom} onChange={e => setDateFrom(e.target.value)}
          title="From" suppressHydrationWarning
        />
        <span style={{ fontSize: 12, color: "var(--on-variant)", flexShrink: 0 }}>to</span>
        <input
          className="field-input" type="date" style={{ width: 140, flexShrink: 0 }}
          value={dateTo} onChange={e => setDateTo(e.target.value)}
          title="To" suppressHydrationWarning
        />

        {hasActiveFilters && (
          <button type="button" className="btn btn-ghost" onClick={clearFilters} style={{ flexShrink: 0 }}>
            <i className="ti ti-x" /> Clear
          </button>
        )}
      </form>

      {/* ── Resend feedback ─────────────────────────────────────────────── */}
      {resendMsg && (
        <div className="alert alert-success" style={{ marginBottom: 16 }}>
          <i className="ti ti-circle-check" /><div>{resendMsg}</div>
          <button style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer" }} onClick={() => setResendMsg(null)}>✕</button>
        </div>
      )}
      {resendErr && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <i className="ti ti-alert-circle" /><div>{resendErr}</div>
          <button style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer" }} onClick={() => setResendErr(null)}>✕</button>
        </div>
      )}

      {apiError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> {apiError}
        </div>
      )}

      {/* ── Table ───────────────────────────────────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <i className="ti ti-mail" /> {pageData?.count ?? 0} Email{pageData?.count !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>To</th>
                <th>Subject</th>
                <th>Module</th>
                <th>Template</th>
                <th>Status</th>
                <th>Sent By</th>
                <th>Sent At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>No emails found.</td></tr>
              )}
              {rows.map(row => (
                <tr key={row.id}>
                  <td style={{ fontSize: 12 }}>{row.recipient_email}</td>
                  <td>{row.subject || "—"}</td>
                  <td>
                    <span className={`badge ${moduleClass(row.module)}`} style={{ textTransform: "capitalize" }}>
                      {row.module || "—"}
                    </span>
                  </td>
                  <td style={{ color: "var(--on-variant)", fontSize: 12 }}>{row.template_name || "—"}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span className={`badge ${row.status === "sent" ? "badge-success" : "badge-error"}`}>
                        {row.status === "sent" ? "Sent" : "Failed"}
                      </span>
                      {row.is_resend && (
                        <span className="badge badge-neutral" style={{ fontSize: 10 }}>Resend</span>
                      )}
                    </div>
                  </td>
                  <td>{row.triggered_by_name || "—"}</td>
                  <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{fmtDateTime(row.created_at)}</td>
                  <td>
                    {row.status === "failed" && canResend && (
                      <button
                        className="btn btn-filled btn-sm"
                        style={{ fontSize: ".78rem" }}
                        onClick={() => handleResend(row)}
                        disabled={resendingId === row.id}
                        suppressHydrationWarning
                      >
                        {resendingId === row.id
                          ? <><i className="ti ti-loader-2 animate-spin" /> Resending…</>
                          : <><i className="ti ti-repeat" /> Resend</>
                        }
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {pageData && pageData.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {pageData.page} of {pageData.total_pages}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= pageData.total_pages} onClick={() => setPage(p => Math.min(p + 1, pageData.total_pages))}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
