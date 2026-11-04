"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { CustomerRow, SubscriptionPlan } from "@/types/platformAdmin";
import SaasTabs, { PAYMENT_BADGE, PROVISION_BADGE, fmtDate } from "../_components/SaasTabs";
import AssignSubscriptionModal from "../_components/AssignSubscriptionModal";
import SubscriptionDetailModal from "../_components/SubscriptionDetailModal";

interface Page { count: number; results: CustomerRow[] }

export default function SubscriptionsPage() {
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => { const t = setTimeout(() => setQ(search.trim()), 300); return () => clearTimeout(t); }, [search]);
  const { data, loading, error, refetch } = useFetch<Page>(
    `${API.platformAdmin.saas.subscriptions}?page_size=100${q ? `&search=${encodeURIComponent(q)}` : ""}`, platformAdminApi);
  const { data: plans } = useFetch<SubscriptionPlan[]>(API.platformAdmin.saas.plans, platformAdminApi);
  const [assign, setAssign] = useState<CustomerRow | null | "open">(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const rows = data?.results ?? [];

  return (
    <div className="saas-page">
      <SaasTabs title="Customer Subscriptions" sub="Every company, its plan and modules"
        actions={<button className="btn btn-filled" onClick={() => setAssign("open")} disabled={!plans}><i className="ti ti-plus" /> Add customer / assign</button>} />
      {msg && <div className="alert alert-success mb-16">{msg}</div>}
      {error && <div className="alert alert-error mb-16">{error}</div>}

      <div className="filter-bar" style={{ marginBottom: 12 }}>
        <input className="field-input" style={{ width: 280, maxWidth: "100%" }} placeholder="Search company name or code" value={search}
          onChange={e => setSearch(e.target.value)} />
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Company</th><th>Contact</th><th>Plan</th><th>Source</th><th>Employees</th><th>Period</th><th>Status</th><th>Payment</th><th>Provisioning</th><th /></tr>
            </thead>
            <tbody>
              {loading && rows.length === 0 && <tr><td colSpan={10}>Loading…</td></tr>}
              {!loading && rows.length === 0 && <tr><td colSpan={10}>No companies found.</td></tr>}
              {rows.map(c => {
                const s = c.subscription;
                return (
                  <tr key={c.id}>
                    <td><strong>{c.company_name}</strong><div style={{ fontSize: 12, color: "var(--on-variant)" }}>{c.company_code}</div></td>
                    <td>{c.contact_name || "—"}</td>
                    <td>{s ? s.plan_name : <span className="badge badge-warn">Not assigned</span>}</td>
                    <td style={{ textTransform: "capitalize" }}>{s?.source ?? "—"}</td>
                    <td>{s?.employee_count ?? c.expected_employee_count ?? "—"}</td>
                    <td style={{ fontSize: 12 }}>{s ? `${fmtDate(s.starts_on)} – ${s.ends_on ? fmtDate(s.ends_on) : "no end"}` : "—"}</td>
                    <td>{s ? <span className={`badge ${s.status === "active" ? "badge-success" : "badge-neutral"}`} style={{ textTransform: "capitalize" }}>{s.status}</span> : "—"}</td>
                    <td>
                      {s ? (
                        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 4 }}>
                          <span className={`badge ${PAYMENT_BADGE[s.payment_status].cls}`}>{PAYMENT_BADGE[s.payment_status].label}</span>
                          {s.unconfirmed_payments > 0 && (
                            <span className="badge badge-info" title="Recorded payments awaiting confirmation">{s.unconfirmed_payments} to confirm</span>
                          )}
                        </div>
                      ) : "—"}
                    </td>
                    <td>
                      {s ? <span className={`badge ${PROVISION_BADGE[s.provisioning_status].cls}`}>{PROVISION_BADGE[s.provisioning_status].label}</span>
                        : <span className={`badge ${c.provisioning_status === "active" ? "badge-success" : c.provisioning_status === "failed" ? "badge-error" : "badge-neutral"}`}
                          style={{ textTransform: "capitalize" }}>{c.provisioning_status}</span>}
                    </td>
                    <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                      {!s && <button className="btn btn-ghost btn-sm" onClick={() => setAssign(c)}>Assign</button>}
                      <button className="btn btn-ghost btn-sm" onClick={() => setDetail(c.id)}>View</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {assign && plans && (
        <AssignSubscriptionModal customers={rows} plans={plans} preselect={assign === "open" ? null : assign}
          onClose={() => setAssign(null)} onDone={m => { setMsg(m); refetch(); }} />
      )}
      {detail && plans && (
        <SubscriptionDetailModal customerId={detail} plans={plans} onClose={() => setDetail(null)} onChanged={refetch} />
      )}
    </div>
  );
}
