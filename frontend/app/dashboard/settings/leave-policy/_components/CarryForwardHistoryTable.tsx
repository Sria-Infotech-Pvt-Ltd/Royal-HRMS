"use client";

import type { CarryForwardHistoryResponse } from "@/types/leave";
import { formatDateTime } from "@/lib/formatDate";

interface Props {
  history: CarryForwardHistoryResponse | null;
  loading: boolean;
  page:    number;
  onPageChange: (page: number) => void;
}

function fmtDateTime(iso: string): string {
  if (!iso) return "—";
  return formatDateTime(iso);
}

export default function CarryForwardHistoryTable({ history, loading, page, onPageChange }: Props) {
  const results    = history?.results ?? [];
  const totalPages = history?.total_pages ?? 1;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-history" /> Carry Forward History</div>
      </div>

      {loading ? (
        <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> &nbsp;Loading history…
        </div>
      ) : results.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-history-toggle" />
          <h3>No history yet</h3>
          <p>No carry-forward runs have been executed yet.</p>
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Executed By</th>
                  <th style={{ textAlign: "center" }}>Processed</th>
                  <th style={{ textAlign: "center" }}>Skipped</th>
                  <th style={{ textAlign: "center" }}>Failed</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {results.map(log => (
                  <tr key={log.id}>
                    <td style={{ fontWeight: 600 }}>{log.from_year} → {log.to_year}</td>
                    <td>{log.executed_by_name}</td>
                    <td style={{ textAlign: "center", color: "var(--success)", fontWeight: 600 }}>{log.total_processed}</td>
                    <td style={{ textAlign: "center", color: "var(--on-variant)" }}>{log.total_skipped}</td>
                    <td style={{ textAlign: "center", fontWeight: 600, color: log.total_failed > 0 ? "var(--error)" : "var(--on-variant)" }}>{log.total_failed}</td>
                    <td style={{ textAlign: "center" }}>
                      {log.is_completed
                        ? <span className="badge badge-success">Completed</span>
                        : <span className="badge badge-warn">Incomplete</span>}
                    </td>
                    <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{fmtDateTime(log.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
              <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {page} of {totalPages}</span>
              <div style={{ display: "flex", gap: 6 }}>
                <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onPageChange(Math.max(page - 1, 1))}>
                  <i className="ti ti-chevron-left" /> Prev
                </button>
                <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => onPageChange(Math.min(page + 1, totalPages))}>
                  Next <i className="ti ti-chevron-right" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
