"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

// ─── Types ────────────────────────────────────────────────────────────────────

type LogEntry = {
  id:          number;
  actor_name:  string;
  actor_email: string | null;
  actor_role:  string | null;
  action:      string;
  module:      string;
  object_id:   string;
  ip_address:  string | null;
  created_at:  string;
};

type PageData = {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     LogEntry[];
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const MODULES = [
  { value: 'accounts', label: 'Accounts' },
  { value: 'settings', label: 'Settings' },
  { value: 'company',  label: 'Company'  },
  { value: 'branch',        label: 'Branch'        },
  { value: 'announcements', label: 'Announcements' },
];

function actionClass(action: string): string {
  if (action.endsWith('_created') || action === 'create')               return 'badge-success';
  if (action.endsWith('_deleted') || action === 'delete')               return 'badge-error';
  if (action.endsWith('_updated') || action === 'update')               return 'badge-warn';
  if (action.endsWith('_activated'))                                    return 'badge-info';
  if (action === 'login')                                               return 'badge-info';
  if (action === 'logout')                                              return 'badge-neutral';
  if (action.startsWith('password') || action.startsWith('password_')) return 'badge-primary';
  return 'badge-neutral';
}

function moduleClass(module: string): string {
  switch (module) {
    case 'accounts': return 'badge-primary';
    case 'settings': return 'badge-warn';
    case 'company':  return 'badge-info';
    case 'branch':        return 'badge-success';
    case 'announcements': return 'badge-error';
    default:              return 'badge-neutral';
  }
}

function fmtAction(action: string): string {
  return action.replace(/_/g, ' ');
}

function isoToday(): string {
  return new Date().toISOString().split('T')[0];
}

function iso30DaysAgo(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().split('T')[0];
}

function fmtDateTime(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
    time: d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }),
  };
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function AuditLogPage() {
  const router = useRouter();

  const [pageData,  setPageData]  = useState<PageData | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [apiError,  setApiError]  = useState<string | null>(null);

  // Filters
  const [module,    setModule]    = useState('');
  const [search,    setSearch]    = useState('');
  const [dateFrom,  setDateFrom]  = useState(iso30DaysAgo());
  const [dateTo,    setDateTo]    = useState(isoToday());
  const [page,      setPage]      = useState(1);

  const searchRef = useRef<HTMLInputElement>(null);

  // ─── Fetch ────────────────────────────────────────────────────────────────

  const fetchLogs = useCallback(async (pg: number) => {
    setLoading(true);
    setApiError(null);
    try {
      const params: Record<string, string> = { page: String(pg), page_size: '10' };
      if (module)   params.module    = module;
      if (search)   params.search    = search;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo)   params.date_to   = dateTo;

      const res = await clientApi.get(API.settings.audit, { params });
      setPageData(res.data?.data ?? null);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setApiError(e.message ?? 'Failed to load audit logs.');
    } finally {
      setLoading(false);
    }
  }, [module, search, dateFrom, dateTo]);

  // Auto-fetch when module or dates change (not on every search keystroke)
  useEffect(() => {
    setPage(1);
    fetchLogs(1);
  }, [module, dateFrom, dateTo, fetchLogs]);

  // Fetch when page changes
  useEffect(() => {
    fetchLogs(page);
  }, [page, fetchLogs]);

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    fetchLogs(1);
  }

  function clearFilters() {
    setModule('');
    setSearch('');
    setDateFrom(iso30DaysAgo());
    setDateTo(isoToday());
    setPage(1);
  }

  const hasActiveFilters = module || search || dateFrom !== iso30DaysAgo() || dateTo !== isoToday();

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <>
      {/* ── Page header ─────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <div className="page-title">Audit Log</div>
          <div className="page-sub">Immutable record of all system actions across every module</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push('/dashboard/settings')}>
            <i className="ti ti-arrow-left" /> Back
          </button>
        </div>
      </div>

      {/* ── Filters ─────────────────────────────────────────────────────── */}
      <div className="card mb-24">
        <div style={{ padding: '16px 20px', display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'flex-end' }}>
          {/* Module */}
          <div className="field-group" style={{ minWidth: 150 }}>
            <label className="field-label">Module</label>
            <select className="field-input" value={module} onChange={e => setModule(e.target.value)}>
              <option value="">All modules</option>
              {MODULES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>

          {/* Date from */}
          <div className="field-group" style={{ minWidth: 140 }}>
            <label className="field-label">From</label>
            <input className="field-input" type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
          </div>

          {/* Date to */}
          <div className="field-group" style={{ minWidth: 140 }}>
            <label className="field-label">To</label>
            <input className="field-input" type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} />
          </div>

          {/* Actor search */}
          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: 6, alignItems: 'flex-end' }}>
            <div className="field-group" style={{ minWidth: 200 }}>
              <label className="field-label">Actor</label>
              <div className="search-bar" style={{ padding: '7px 10px' }}>
                <i className="ti ti-search" />
                <input
                  ref={searchRef}
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Name or email…"
                />
              </div>
            </div>
            <button className="btn btn-ghost" type="submit" style={{ marginBottom: 1 }}>
              <i className="ti ti-search" /> Search
            </button>
          </form>

          {hasActiveFilters && (
            <button className="btn btn-ghost" onClick={clearFilters} style={{ marginBottom: 1 }}>
              <i className="ti ti-x" /> Clear
            </button>
          )}
        </div>
      </div>

      {/* ── Error ───────────────────────────────────────────────────────── */}
      {apiError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" />
          <div>{apiError}</div>
        </div>
      )}

      {/* ── Table ───────────────────────────────────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <i className="ti ti-history" /> Activity
          </div>
          {pageData && (
            <span style={{ fontSize: 12, color: 'var(--on-variant)' }}>
              {pageData.count.toLocaleString()} entries
            </span>
          )}
        </div>

        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, gap: 10, color: 'var(--on-variant)' }}>
            <i className="ti ti-loader-2" style={{ fontSize: 22, animation: 'spin 1s linear infinite' }} />
            Loading…
          </div>
        ) : !pageData || pageData.results.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-history" />
            <h3>No audit entries found</h3>
            <p>Try adjusting the filters or date range.</p>
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Actor</th>
                    <th style={{ textAlign: 'center' }}>Module</th>
                    <th style={{ textAlign: 'center' }}>Action</th>
                    <th>IP Address</th>
                  </tr>
                </thead>
                <tbody>
                  {pageData.results.map(log => {
                    const { date, time } = fmtDateTime(log.created_at);
                    return (
                      <tr key={log.id}>
                        {/* Timestamp */}
                        <td style={{ whiteSpace: 'nowrap' }}>
                          <div style={{ fontWeight: 500, fontSize: 13 }}>{date}</div>
                          <div style={{ fontSize: 11, color: 'var(--on-variant)' }}>{time}</div>
                        </td>

                        {/* Actor */}
                        <td>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{log.actor_name}</div>
                          {log.actor_email && (
                            <div style={{ fontSize: 11, color: 'var(--on-variant)' }}>{log.actor_email}</div>
                          )}
                          {log.actor_role && (
                            <div style={{ marginTop: 3 }}>
                              <span className="badge badge-neutral" style={{ fontSize: 10 }}>{log.actor_role}</span>
                            </div>
                          )}
                        </td>

                        {/* Module */}
                        <td style={{ textAlign: 'center' }}>
                          <span className={`badge ${moduleClass(log.module)}`} style={{ textTransform: 'capitalize' }}>
                            {log.module}
                          </span>
                        </td>

                        {/* Action */}
                        <td style={{ textAlign: 'center' }}>
                          <span className={`badge ${actionClass(log.action)}`} style={{ textTransform: 'capitalize', whiteSpace: 'nowrap' }}>
                            {fmtAction(log.action)}
                          </span>
                        </td>

                        {/* IP */}
                        <td>
                          <code style={{ fontSize: 12, color: 'var(--on-variant)', background: 'var(--bg-low)', padding: '2px 6px', borderRadius: 4 }}>
                            {log.ip_address ?? '—'}
                          </code>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* ── Pagination ──────────────────────────────────────────── */}
            {pageData.total_pages > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 20px', borderTop: '1px solid var(--outline-v)' }}>
                <span style={{ fontSize: 12, color: 'var(--on-variant)' }}>
                  Page {pageData.page} of {pageData.total_pages}
                </span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={pageData.page <= 1}
                    onClick={() => setPage(p => Math.max(p - 1, 1))}
                  >
                    <i className="ti ti-chevron-left" /> Prev
                  </button>

                  {/* Page number pills — show up to 5 around current */}
                  {Array.from({ length: pageData.total_pages }, (_, i) => i + 1)
                    .filter(n => Math.abs(n - pageData.page) <= 2)
                    .map(n => (
                      <button
                        key={n}
                        className="btn btn-sm"
                        style={{
                          background: n === pageData.page ? 'var(--primary)' : 'transparent',
                          color:      n === pageData.page ? '#fff' : 'var(--on-variant)',
                          border:     n === pageData.page ? 'none' : '1.5px solid var(--outline-v)',
                          minWidth:   32,
                        }}
                        onClick={() => setPage(n)}
                      >
                        {n}
                      </button>
                    ))}

                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={pageData.page >= pageData.total_pages}
                    onClick={() => setPage(p => Math.min(p + 1, pageData.total_pages))}
                  >
                    Next <i className="ti ti-chevron-right" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
