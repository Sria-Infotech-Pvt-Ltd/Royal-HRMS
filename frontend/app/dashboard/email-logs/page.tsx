"use client";

import { useCallback, useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import { formatDateTime } from "@/lib/formatDate";
import DateInput from "@/components/shared/DateInput";
import { shiftISODate } from "@/app/dashboard/attendance/_components/attendanceDates";
import { localISODate } from "@/app/dashboard/attendance/_components/monthView";
import EmailLogRow, { type EmailLogEntry } from "./_components/EmailLogRow";
import { EmailLogStyles } from "./_components/emailLogStyles";

// ─── Types ────────────────────────────────────────────────────────────────────

type PageData = {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     EmailLogEntry[];
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
  return localISODate();
}

function iso30DaysAgo(): string {
  return shiftISODate(localISODate(), -30);
}

function fmtDateTime(iso: string): string {
  return formatDateTime(iso);
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

  async function handleResend(row: EmailLogEntry) {
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
  const failedOnPage = rows.filter(row => row.status === "failed").length;

  return (
    <>
      <EmailLogStyles />
      <div className="page-header">
        <div>
          <div className="page-title">Email Logs</div>
          <div className="page-sub">System-wide email delivery history and status</div>
        </div>
      </div>

      {/* ── Filters ─────────────────────────────────────────────────────── */}
      <form onSubmit={handleSearchSubmit} className="el-filters card">
        <div className="el-filter-row">
          <label className="el-f el-f-grow">
            <span>Recipient or subject</span>
            <div className="el-search">
              <i className="ti ti-search" />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by recipient or subject…" suppressHydrationWarning />
            </div>
          </label>
          <label className="el-f">
            <span>Module</span>
            <select className="field-input field-select" value={module} onChange={e => setModule(e.target.value)} suppressHydrationWarning>
              <option value="">All modules</option>
              {MODULES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </label>
          <div className="el-dates">
            <div className="el-f"><span>From</span><DateInput className="field-input" value={dateFrom} onChange={isoDate => setDateFrom(isoDate)} title="From" /></div>
            <b>to</b>
            <div className="el-f"><span>To</span><DateInput className="field-input" value={dateTo} onChange={isoDate => setDateTo(isoDate)} title="To" /></div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" className="btn btn-filled" style={{ height: 42 }}><i className="ti ti-search" /> Search</button>
            {hasActiveFilters && (
              <button type="button" className="btn btn-ghost" style={{ height: 42 }} onClick={clearFilters}><i className="ti ti-x" /> Clear</button>
            )}
          </div>
        </div>

        <div className="el-chips" role="group" aria-label="Delivery status">
          {([
            { key: "", label: "All emails", icon: "ti-mail", accent: "var(--brand)" },
            { key: "sent", label: "Sent", icon: "ti-mail-check", accent: "#16a34a" },
            { key: "failed", label: "Failed", icon: "ti-mail-exclamation", accent: "#dc2626" },
          ] as const).map(chip => (
            <button
              key={chip.key || "all"} type="button" aria-pressed={status === chip.key}
              className={`el-chip${status === chip.key ? " is-on" : ""}`} style={{ "--el-accent": chip.accent } as React.CSSProperties}
              onClick={() => setStatus(chip.key)}
            >
              <i className={`ti ${chip.icon}`} /> {chip.label}
            </button>
          ))}
          {pageData && (
            <div className="el-strip">
              <span className="el-stat" style={{ "--el-stat": "var(--brand)" } as React.CSSProperties}><i className="ti ti-mails" /> Total <b>{pageData.count}</b></span>
              <span className={`el-stat${failedOnPage > 0 ? " is-urgent" : ""}`} style={{ "--el-stat": "#dc2626" } as React.CSSProperties}><i className="ti ti-alert-triangle" /> Failed on this page <b>{failedOnPage}</b></span>
            </div>
          )}
        </div>
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
                <th className="el-hide-md">Module</th>
                <th className="el-hide-md">Template</th>
                <th>Status</th>
                <th className="el-hide-md">Sent By</th>
                <th>Sent At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={8}><div className="el-empty"><i className="ti ti-mail-off" />No emails found for these filters.</div></td></tr>
              )}
              {rows.map(row => (
                <EmailLogRow
                  key={row.id} row={row} moduleClass={moduleClass(row.module)} sentAt={fmtDateTime(row.created_at)}
                  canResend={canResend} isResending={resendingId === row.id} onResend={handleResend}
                />
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
