"use client";

// Platform Admin → SaaS → Customer Registrations (website sign-ups).
// Approve needs a verified payment AND a pending registration — the server
// enforces both; the button only reflects them. Approval creates the company
// with the normal provisioning and assigns the paid plan.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import FieldError from "@/components/FieldError";
import * as v from "@/lib/saasValidation";
import type { CompanyRegistration } from "@/types/platformAdmin";
import SaasTabs, { apiMessage, fmtDate, fmtMoney } from "../_components/SaasTabs";

const FILTERS = [
  { value: "pending_approval", label: "Waiting for approval" },
  { value: "awaiting_payment", label: "Waiting for payment" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "", label: "All" },
];

function statusOf(r: CompanyRegistration): { label: string; cls: string } {
  if (r.approval_status === "rejected") return { label: "Rejected", cls: "badge-neutral" };
  if (r.approval_status === "approved") {
    if (r.provisioning_status === "active") return { label: "Active", cls: "badge-success" };
    if (r.provisioning_status === "failed") return { label: "Setup failed", cls: "badge-error" };
    return { label: "Setting up", cls: "badge-info" };
  }
  if (r.payment_status === "paid") return { label: "Waiting for approval", cls: "badge-warn" };
  if (r.payment_status === "failed") return { label: "Payment failed", cls: "badge-error" };
  return { label: "Waiting for payment", cls: "badge-neutral" };
}

function ReviewModal({ reg, onClose, onDone }: { reg: CompanyRegistration; onClose: () => void; onDone: (m: string) => void }) {
  const [code, setCode] = useState(reg.company_code);
  const [reason, setReason] = useState("");
  const codeError = v.companyCode(code);
  const [mode, setMode] = useState<"view" | "approve" | "reject">("view");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const canReview = reg.approval_status === "pending";
  const paid = reg.payment_status === "paid";

  async function act(fn: () => Promise<{ data: { message?: string } }>, fallback: string) {
    setBusy(true);
    setErr(null);
    try {
      const { data } = await fn();
      onDone(data.message ?? "Done.");
      onClose();
    } catch (e) {
      setErr(apiMessage(e, fallback));
    } finally {
      setBusy(false);
    }
  }

  const footer = mode === "approve" ? (
    <>
      <button className="btn btn-ghost" onClick={() => setMode("view")} disabled={busy}>Back</button>
      <button className="btn btn-filled" disabled={busy || !!codeError}
        onClick={() => act(() => platformAdminApi.post(API.platformAdmin.saas.approveRegistration(reg.id),
          code.trim().toUpperCase() !== reg.company_code ? { company_code: code.trim() } : {}), "Could not approve.")}>
        {busy ? "Approving…" : "Yes, approve and set up the company"}
      </button>
    </>
  ) : mode === "reject" ? (
    <>
      <button className="btn btn-ghost" onClick={() => setMode("view")} disabled={busy}>Back</button>
      <button className="btn btn-filled" style={{ background: "var(--error)" }} disabled={busy || !reason.trim()}
        onClick={() => act(() => platformAdminApi.post(API.platformAdmin.saas.rejectRegistration(reg.id), { reason }), "Could not reject.")}>
        {busy ? "Rejecting…" : "Reject registration"}
      </button>
    </>
  ) : (
    <>
      {reg.approval_status === "approved" && reg.provisioning_status === "failed" && reg.client_id && (
        <button className="btn btn-ghost" disabled={busy} style={{ marginRight: "auto" }}
          onClick={() => act(() => platformAdminApi.post(API.platformAdmin.companies.retryProvisioning(reg.client_id!), { admin_email: reg.admin_email }),
            "Could not start the retry.")}>
          <i className="ti ti-refresh" /> Retry provisioning
        </button>
      )}
      <button className="btn btn-ghost" onClick={onClose}>Close</button>
      {canReview && <button className="btn btn-ghost" onClick={() => setMode("reject")}>Reject…</button>}
      {canReview && (
        <button className="btn btn-filled" onClick={() => setMode("approve")} disabled={!paid}
          title={paid ? "" : "Approval needs a verified payment"}>Approve…</button>
      )}
    </>
  );

  const rows: [string, string][] = [
    ["Company", `${reg.company_name} (${reg.company_code})`],
    ["Contact", `${reg.contact_name} · ${reg.contact_phone}`],
    ["Admin email (login)", reg.admin_email],
    ["GSTIN", reg.gstin || "—"],
    ["Address", reg.address || "—"],
    ["Plan", `${reg.plan_name} · ${reg.billing_period} · ${reg.employee_count} employees`],
    ["Amount", `${fmtMoney(reg.subtotal, reg.currency)} + GST ${fmtMoney(reg.gst_amount, reg.currency)}${reg.gst_inclusive ? " (included)" : ""} = ${fmtMoney(reg.total, reg.currency)}`],
    ["Payment", reg.payment_status === "paid" ? `Paid ${reg.paid_at ? fmtDate(reg.paid_at) : ""}` : reg.payment_status],
    ["Submitted", new Date(reg.created_at).toLocaleString("en-IN")],
  ];
  if (reg.reviewed_at) rows.push(["Reviewed", `${reg.reviewed_by_name ?? "—"} · ${new Date(reg.reviewed_at).toLocaleString("en-IN")}`]);
  if (reg.rejection_reason) rows.push(["Rejection reason", reg.rejection_reason]);
  if (reg.refund_status) rows.push(["Refund", reg.refund_status === "pending" ? "Pending (per refund policy)" : reg.refund_status]);

  return (
    <Modal title={`Registration ${reg.reference}`} onClose={onClose} closeDisabled={busy} size="lg" footer={footer}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14, fontSize: 13 }}>
        {err && <div className="alert alert-error">{err}</div>}
        {canReview && !paid && (
          <div className="alert alert-info">Waiting for a verified online payment. It can be approved only after the payment gateway confirms payment.</div>
        )}
        <table className="data-table" style={{ width: "100%" }}>
          <tbody>{rows.map(([k, v]) => <tr key={k}><td style={{ width: 170, color: "var(--on-variant)" }}>{k}</td><td>{v}</td></tr>)}</tbody>
        </table>
        <div><strong>Modules on approval:</strong> {reg.modules.length ? reg.modules.join(", ") : "core only"}</div>
        {reg.payments.length > 0 && (
          <table className="data-table" style={{ width: "100%", fontSize: 12 }}>
            <thead><tr><th>Gateway</th><th>Order</th><th>Payment</th><th>Amount</th><th>Status</th><th>When</th></tr></thead>
            <tbody>
              {reg.payments.map(p => (
                <tr key={p.order_id}>
                  <td>{p.gateway}</td><td>{p.order_id}</td><td>{p.payment_id ?? "—"}</td>
                  <td>{fmtMoney(p.amount_minor / 100, p.currency)}</td>
                  <td>{p.status}{p.failure_reason ? ` — ${p.failure_reason}` : ""}</td>
                  <td>{new Date(p.created_at).toLocaleString("en-IN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {mode === "approve" && (
          <div className="alert alert-warn" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
            <div>Approving creates the company with the plan&apos;s modules and sends the activation email to {reg.admin_email} when setup finishes.</div>
            <label className="field-label">Company code (login code)</label>
            <input className="field-input" value={code} onChange={e => setCode(e.target.value.toUpperCase())} maxLength={20} style={{ maxWidth: 220 }} />
            <FieldError msg={codeError} />
          </div>
        )}
        {mode === "reject" && (
          <div className="field-group">
            <label className="field-label">Reason (kept on record) *</label>
            <textarea className="field-input" rows={3} maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} />
            {paid && <span style={{ fontSize: 12, color: "var(--on-variant)" }}>This registration is paid — it will be marked for refund per the refund policy.</span>}
          </div>
        )}
      </div>
    </Modal>
  );
}

export default function RegistrationsPage() {
  const [filter, setFilter] = useState("pending_approval");
  const [search, setSearch] = useState("");
  const qs = new URLSearchParams({ page_size: "100", ...(filter ? { status: filter } : {}), ...(search.trim() ? { search: search.trim() } : {}) });
  const { data, loading, error, refetch } = useFetch<{ count: number; results: CompanyRegistration[] }>(
    `${API.platformAdmin.saas.registrations}?${qs}`, platformAdminApi);
  const [open, setOpen] = useState<CompanyRegistration | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const rows = data?.results ?? [];

  return (
    <div className="saas-page">
      <SaasTabs title="Customer Registrations" sub="Website sign-ups — approve after a verified payment" />
      {msg && <div className="alert alert-success mb-16">{msg}</div>}
      {error && <div className="alert alert-error mb-16">{error}</div>}
      <div className="filter-bar" style={{ marginBottom: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
        <select className="field-input" style={{ width: 220 }} value={filter} onChange={e => setFilter(e.target.value)}>
          {FILTERS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
        </select>
        <input className="field-input" style={{ width: 260 }} placeholder="Reference, company name or code" value={search}
          onChange={e => setSearch(e.target.value)} />
      </div>
      <div className="card">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Reference</th><th>Company</th><th>Plan</th><th>Employees</th><th>Total</th><th>Status</th><th>Submitted</th><th /></tr></thead>
            <tbody>
              {loading && rows.length === 0 && <tr><td colSpan={8}>Loading…</td></tr>}
              {!loading && rows.length === 0 && <tr><td colSpan={8}>No registrations.</td></tr>}
              {rows.map(r => {
                const s = statusOf(r);
                return (
                  <tr key={r.id}>
                    <td style={{ fontFamily: "monospace" }}>{r.reference}</td>
                    <td><strong>{r.company_name}</strong><div style={{ fontSize: 12, color: "var(--on-variant)" }}>{r.company_code}</div></td>
                    <td>{r.plan_name} <span style={{ fontSize: 12, color: "var(--on-variant)" }}>({r.billing_period})</span></td>
                    <td>{r.employee_count}</td>
                    <td>{fmtMoney(r.total, r.currency)}</td>
                    <td><span className={`badge ${s.cls}`}>{s.label}</span></td>
                    <td style={{ fontSize: 12 }}>{fmtDate(r.created_at)}</td>
                    <td style={{ textAlign: "right" }}><button className="btn btn-ghost btn-sm" onClick={() => setOpen(r)}>Review</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      {open && <ReviewModal reg={open} onClose={() => setOpen(null)} onDone={m => { setMsg(m); refetch(); }} />}
    </div>
  );
}
