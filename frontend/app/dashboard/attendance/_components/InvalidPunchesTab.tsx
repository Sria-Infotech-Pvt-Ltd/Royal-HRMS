"use client";

// Invalid Punches is on hold until the resolution workflow (Fix action, endpoints
// for assign/convert/discard) is finalized with backend. The table below is kept
// commented out so it can be restored once that contract is defined.

// import { useState } from "react";
// import { useFetch } from "@/hooks/useFetch";
// import { API } from "@/lib/api/endpoints";
// import type { PaginatedInvalidPunches } from "@/types/attendance";

// const ISSUE_BADGE: Record<string, string> = {
//   "no-match":  "badge badge-error",
//   duplicate:   "badge badge-warn",
//   future:      "badge badge-error",
// };

export default function InvalidPunchesTab() {
  // const [page, setPage] = useState(1);
  // const { data, loading, error } =
  //   useFetch<PaginatedInvalidPunches>(`${API.attendance.invalidPunches}?page=${page}&page_size=20`);
  // const rows = data?.results ?? [];

  return (
    <div className="empty-state card">
      <i className="ti ti-tools" />
      <h3>Coming Soon</h3>
      <p>Invalid punch resolution is being finalized and will be available here soon.</p>
    </div>
  );

  /*
  return (
    <>
      <div className="alert alert-info mb-16">
        <i className="ti ti-alert-circle" />
        <span>
          These punches could not be matched to an employee or contain data errors.
          Review and fix each record before it affects payroll.
        </span>
      </div>

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Device ID</th>
                <th>Raw Punch Time</th>
                <th>Card / Bio ID</th>
                <th>Issue</th>
                <th>Suggested Match</th>
                <th>Branch</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={7} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>No invalid punches found.</td></tr>
              )}
              {rows.map(p => (
                <tr key={p.id}>
                  <td>
                    <span style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: "var(--on-bg)", fontWeight: 600 }}>
                      {p.device_id}
                    </span>
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{p.raw_time}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{p.biometric_id}</td>
                  <td><span className={ISSUE_BADGE[p.issue_type] ?? "badge badge-neutral"}>{p.issue}</span></td>
                  <td style={{ color: "var(--on-variant)", fontSize: 12 }}>{p.suggested_match}</td>
                  <td>{p.branch}</td>
                  <td>
                    <button className="btn btn-outline btn-sm" style={{ padding: "3px 10px", fontSize: 11 }}>
                      <i className="ti ti-tool" /> Fix
                    </button>
                  </td>
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
  */
}
