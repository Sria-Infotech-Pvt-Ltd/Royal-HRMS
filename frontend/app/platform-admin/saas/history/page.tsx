"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { SubscriptionHistoryEntry } from "@/types/platformAdmin";
import SaasTabs, { EVENT_LABEL, planChange } from "../_components/SaasTabs";

function modulesOf(x: Record<string, unknown>): string {
  const m = (x.modules ?? x.modules_before) as string[] | undefined;
  return Array.isArray(m) ? (m.length ? m.join(", ") : "core only") : "—";
}

const PAGE_SIZE = 20;

// 1 … 4 5 6 … 20 — first, last, and the pages around the current one.
function pageWindow(page: number, total: number): (number | "…")[] {
  const keep = new Set([1, total, page - 1, page, page + 1].filter(p => p >= 1 && p <= total));
  const out: (number | "…")[] = [];
  [...keep].sort((a, b) => a - b).forEach((p, i, arr) => {
    if (i > 0 && p - arr[i - 1] > 1) out.push("…");
    out.push(p);
  });
  return out;
}

interface HistoryPage {
  count: number;
  page: number;
  total_pages: number;
  results: SubscriptionHistoryEntry[];
}

export default function SubscriptionHistoryPage() {
  const [requested, setPage] = useState(1);
  const { data, loading, error } = useFetch<HistoryPage>(
    `${API.platformAdmin.saas.history}?page=${requested}&page_size=${PAGE_SIZE}`, platformAdminApi);
  const page = data?.page ?? requested;          // the server clamps a page past the end
  const rows = data?.results ?? [];
  const total = data?.count ?? 0;
  const totalPages = data?.total_pages ?? 1;

  function go(p: number) {
    setPage(p);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="saas-page">
      <SaasTabs title="Subscription History" sub="Every subscription change, newest first" />
      {error && <div className="alert alert-error mb-16">{error}</div>}
      <div className="card">
        <div className="table-wrap">
          <table style={{ fontSize: 12.5 }}>
            <thead><tr><th>When</th><th>Company</th><th>Event</th><th>Plan</th><th>Modules before</th><th>Modules after</th><th>By</th><th>Note</th></tr></thead>
            <tbody>
              {loading && rows.length === 0 && <tr><td colSpan={8}>Loading…</td></tr>}
              {!loading && rows.length === 0 && <tr><td colSpan={8}>No subscription changes yet.</td></tr>}
              {rows.map(h => (
                <tr key={h.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{new Date(h.created_at).toLocaleString("en-IN")}</td>
                  <td>{h.company_name} <span style={{ color: "var(--on-variant)" }}>({h.company_code})</span></td>
                  <td>{EVENT_LABEL[h.event] ?? h.event}</td>
                  <td>{planChange(h)}</td>
                  <td style={{ maxWidth: 220 }}>{modulesOf(h.before)}</td>
                  <td style={{ maxWidth: 220 }}>{modulesOf(h.after)}</td>
                  <td>{h.admin_name ?? "System"}</td>
                  <td>{h.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {total > 0 && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 16, flexWrap: "wrap", gap: 8 }}>
          <span style={{ fontSize: 13, color: "var(--on-variant)" }}>
            Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total} entries
          </span>
          {totalPages > 1 && (
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1 || loading} onClick={() => go(page - 1)}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              {pageWindow(page, totalPages).map((p, i) => p === "…"
                ? <span key={`gap${i}`} style={{ padding: "0 4px", color: "var(--on-variant)" }}>…</span>
                : (
                  <button key={p} className={`btn btn-sm ${p === page ? "btn-filled" : "btn-ghost"}`}
                    disabled={loading} onClick={() => p !== page && go(p)}>{p}</button>
                ))}
              <button className="btn btn-ghost btn-sm" disabled={page >= totalPages || loading} onClick={() => go(page + 1)}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
