"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

interface CandidateEmail {
  id:                 number;
  template_used:      string;
  subject:            string;
  to_email:           string;
  status:             "sent" | "failed";
  sent_by_name:       string;
  sent_at:            string;
  candidate:          number;
  candidate_name:     string;
  candidate_position: string;
}

interface PaginatedCandidateEmails {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     CandidateEmail[];
}

const STATUS_BADGE: Record<CandidateEmail["status"], string> = {
  sent:   "badge badge-success",
  failed: "badge badge-error",
};

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function EmailLogsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage]     = useState(1);

  const query = new URLSearchParams({ page: String(page), page_size: "20" });
  if (search) query.set("search", search);

  const { data, loading, error } =
    useFetch<PaginatedCandidateEmails>(`${API.recruitment.emailLogs}?${query.toString()}`);
  const rows = data?.results ?? [];

  function handleSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Email Logs</div>
          <div className="page-sub">Recruitment email history and delivery status</div>
        </div>
      </div>

      {error && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> {error}
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <i className="ti ti-mail" /> {data?.count ?? 0} Email{data?.count !== 1 ? "s" : ""}
          </span>
          <div className="search-bar">
            <i className="ti ti-search" />
            <input
              placeholder="Search by candidate or email…"
              value={search}
              onChange={e => handleSearch(e.target.value)}
              suppressHydrationWarning
            />
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Position</th>
                <th>To</th>
                <th>Subject</th>
                <th>Template</th>
                <th>Status</th>
                <th>Sent By</th>
                <th>Sent At</th>
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
                  <td>{row.candidate_name}</td>
                  <td style={{ color: "var(--on-variant)" }}>{row.candidate_position}</td>
                  <td style={{ fontSize: 12 }}>{row.to_email}</td>
                  <td>{row.subject}</td>
                  <td style={{ color: "var(--on-variant)", fontSize: 12 }}>{row.template_used || "—"}</td>
                  <td><span className={STATUS_BADGE[row.status]}>{row.status === "sent" ? "Sent" : "Failed"}</span></td>
                  <td>{row.sent_by_name || "—"}</td>
                  <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{fmtDateTime(row.sent_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data && data.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {data.page} of {data.total_pages}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= data.total_pages} onClick={() => setPage(p => Math.min(p + 1, data.total_pages))}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
