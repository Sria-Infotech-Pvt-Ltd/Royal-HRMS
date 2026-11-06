"use client";

// One customer's subscription: details, payments (record / confirm / reject /
// waive, receipts), change plan (with module difference preview), end date,
// activate / deactivate, history, retry provisioning.

import { useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import type { CustomerRow, PlanChangePreview, SubscriptionHistoryEntry, SubscriptionPaymentRecord, SubscriptionPlan } from "@/types/platformAdmin";
import { EVENT_LABEL, PAYMENT_BADGE, PROVISION_BADGE, apiMessage, fmtDate, fmtMoney, planChange } from "./SaasTabs";
import PaymentsSection from "./PaymentsSection";
import FieldError from "@/components/FieldError";
import * as v from "@/lib/saasValidation";

export default function SubscriptionDetailModal({ customerId, plans, onClose, onChanged }: {
  customerId: string;
  plans: SubscriptionPlan[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const { data, refetch } = useFetch<{ company: CustomerRow; history: SubscriptionHistoryEntry[]; payments: SubscriptionPaymentRecord[] }>(
    API.platformAdmin.saas.subscription(customerId), platformAdminApi);
  const [planId, setPlanId] = useState("");
  const [preview, setPreview] = useState<PlanChangePreview | null>(null);
  const [endsOn, setEndsOn] = useState<string | null>(null);
  const [retryEmail, setRetryEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const company = data?.company;
  const sub = company?.subscription ?? null;
  const retryEmailError = retryEmail.trim() ? v.email(retryEmail) : null;
  const endsOnError = endsOn === null || endsOn === "" ? null
    : v.date(endsOn, { what: "End date" }) ?? (sub && endsOn < sub.starts_on ? "End date cannot be before the start date." : null);
  const choices = plans.filter(p => p.status === "active" && !p.is_legacy && p.id !== sub?.plan);

  async function run(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, text: done });
      refetch();
      onChanged();
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e, "Action failed.") });
    } finally {
      setBusy(false);
    }
  }

  async function previewChange(id: string) {
    setPlanId(id);
    setPreview(null);
    if (!id) return;
    try {
      const { data: r } = await platformAdminApi.post(API.platformAdmin.saas.changePlan(customerId), { plan: id, dry_run: true });
      setPreview(r.data as PlanChangePreview);
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e, "Could not preview the change.") });
    }
  }

  return (
    <Modal title={company ? `${company.company_name} (${company.company_code})` : "Subscription"} onClose={onClose}
      closeDisabled={busy} size="lg" footer={<button className="btn btn-filled" onClick={onClose}>Close</button>}>
      {!company ? <div>Loading…</div> : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16, fontSize: 13 }}>
          {msg && <div className={`alert ${msg.ok ? "alert-success" : "alert-error"}`}>{msg.text}</div>}

          {company.provisioning_status === "failed" && (
            <div className="alert alert-error" style={{ flexWrap: "wrap", gap: 8 }}>
              <span>Provisioning failed. Retry finishes setup without repeating completed steps.</span>
              <input className="field-input" type="email" inputMode="email" maxLength={254} placeholder="Company admin email" value={retryEmail}
                onChange={e => setRetryEmail(e.target.value)} style={{ maxWidth: 240 }} />
              <FieldError msg={retryEmailError} />
              <button className="btn btn-sm btn-filled" disabled={busy || !retryEmail.trim() || !!retryEmailError}
                onClick={() => run(() => platformAdminApi.post(API.platformAdmin.companies.retryProvisioning(company.id), { admin_email: retryEmail }),
                  "Retry started — runs in the background.")}>Retry provisioning</button>
            </div>
          )}

          {!sub ? <div className="alert alert-warn">No subscription assigned yet.</div> : (
            <>
              <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
                {([
                  ["Plan", `${sub.plan_name}${sub.source === "legacy" ? " (legacy)" : ""}`],
                  ["Source", sub.source],
                  ["Status", sub.status],
                  ["Price", `${fmtMoney(sub.price_per_employee, sub.currency)} / employee / month`],
                  ["Employees", sub.employee_count ?? "—"],
                  ["Period", `${fmtDate(sub.starts_on)} – ${sub.ends_on ? fmtDate(sub.ends_on) : "no end date"}`],
                ] as [string, string | number][]).map(([k, v]) => (
                  <div key={k} style={{ background: "var(--bg-low)", borderRadius: 8, padding: "8px 10px" }}>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{k}</div>
                    <div style={{ fontWeight: 600, textTransform: k === "Source" || k === "Status" ? "capitalize" : "none" }}>{v}</div>
                  </div>
                ))}
                {([
                  ["Payment", PAYMENT_BADGE[sub.payment_status]],
                  ["Provisioning", PROVISION_BADGE[sub.provisioning_status]],
                ] as const).map(([k, b]) => (
                  <div key={k} style={{ background: "var(--bg-low)", borderRadius: 8, padding: "8px 10px" }}>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{k}</div>
                    <span className={`badge ${b.cls}`}>{b.label}</span>
                  </div>
                ))}
              </div>

              {sub.provisioning_status === "awaiting_payment" && (
                <div className="alert alert-warn">
                  Awaiting payment — the {sub.plan_name} modules are applied{company.provisioning_status === "awaiting" ? " and the company is set up" : ""} once
                  payment is fully confirmed or waived. {company.provisioning_status === "awaiting" ? "" : "Until then the company keeps its current modules."}
                </div>
              )}
              {sub.provisioning_status === "failed" && company.provisioning_status === "active" && (
                <div className="alert alert-error" style={{ flexWrap: "wrap", gap: 8 }}>
                  <span>{sub.provisioning_error || "The subscription could not be applied."}</span>
                  <button className="btn btn-sm btn-filled" disabled={busy}
                    onClick={() => run(() => platformAdminApi.post(API.platformAdmin.saas.provision(customerId)), "Subscription applied.")}>
                    Apply again
                  </button>
                </div>
              )}

              <PaymentsSection clientId={customerId} sub={sub} payments={data.payments}
                onChanged={() => { refetch(); onChanged(); }} />

              {sub.plan_outdated && sub.latest_plan && (
                <div className="alert alert-info" style={{ flexWrap: "wrap", gap: 8 }}>
                  <span style={{ flex: 1, minWidth: 240 }}>
                    <strong>{sub.plan_name} was edited after this subscription was assigned.</strong> This company keeps
                    its current terms until you apply the latest version (modules and price are recalculated).
                  </span>
                  <button className="btn btn-sm btn-filled" disabled={busy} onClick={() => previewChange(sub.plan)}>
                    Review latest plan
                  </button>
                </div>
              )}

              <div><strong>Modules this company can use:</strong> {(company.effective_modules ?? company.enabled_modules).length
                ? [...(company.effective_modules ?? company.enabled_modules)].sort().join(", ") : "core only"}</div>
              {(sub.extra_modules.length > 0 || sub.removed_modules.length > 0) && (
                <div style={{ color: "var(--on-variant)" }}>
                  Overrides — added: {sub.extra_modules.join(", ") || "none"}; kept off: {sub.removed_modules.join(", ") || "none"}
                </div>
              )}

              <div className="card" style={{ padding: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Change plan</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  <select className="field-input" value={planId} onChange={e => previewChange(e.target.value)} style={{ maxWidth: 280 }}>
                    <option value="">Select a plan…</option>
                    {choices.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                  <button className="btn btn-sm btn-filled" disabled={busy || !planId || !preview}
                    onClick={() => run(() => platformAdminApi.post(API.platformAdmin.saas.changePlan(customerId), { plan: planId }),
                      preview?.same_plan ? "Latest plan version applied." : "Plan changed.").then(() => { setPlanId(""); setPreview(null); })}>
                    {preview?.same_plan ? "Apply latest plan" : "Change plan"}
                  </button>
                </div>
                {preview && (
                  <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
                    {preview.pricing ? (
                      <div style={{ background: "var(--bg-low)", borderRadius: 8, padding: "8px 10px" }}>
                        <div>
                          <strong>Price:</strong> {fmtMoney(preview.pricing.from.price_per_employee, preview.pricing.from.currency)} ({preview.pricing.from.plan})
                          {" → "}<strong>{fmtMoney(preview.pricing.to.price_per_employee, preview.pricing.to.currency)}</strong> ({preview.pricing.to.plan}) / employee / month
                        </div>
                        <div>
                          <strong>Amount due:</strong> {preview.pricing.from.amount_due !== null ? fmtMoney(preview.pricing.from.amount_due, preview.pricing.from.currency) : "not set"}
                          {" → "}<strong>{fmtMoney(preview.pricing.to.amount_due, preview.pricing.to.currency)}</strong>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                          {preview.pricing.employee_count} employees × {preview.pricing.to.months} month(s) ({preview.pricing.billing_period})
                          {" = "}{fmtMoney(preview.pricing.to.subtotal, preview.pricing.to.currency)}
                          {preview.pricing.to.gst_inclusive
                            ? ` (GST ${Number(preview.pricing.to.gst_rate)}% included: ${fmtMoney(preview.pricing.to.gst_amount, preview.pricing.to.currency)})`
                            : ` + GST ${Number(preview.pricing.to.gst_rate)}% ${fmtMoney(preview.pricing.to.gst_amount, preview.pricing.to.currency)}`}
                        </div>
                      </div>
                    ) : (
                      <div style={{ color: "var(--on-variant)" }}>Employee count not set — the amount due won&apos;t be recalculated (set it in Payments).</div>
                    )}
                    {preview.difference.added.length === 0 && preview.difference.removed.length === 0 ? <div>No module changes.</div> : (
                      <>
                        {preview.difference.added.length > 0 && <div style={{ color: "var(--success)" }}>Switched on: {preview.difference.added.join(", ")}</div>}
                        {preview.difference.removed.length > 0 && <div style={{ color: "var(--error)" }}><strong>Switched off: {preview.difference.removed.join(", ")}</strong> — the company loses access to these.</div>}
                      </>
                    )}
                  </div>
                )}
              </div>

              <div className="card" style={{ padding: 12, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ fontWeight: 600 }}>End date</span>
                <input className="field-input" type="date" min={sub.starts_on} value={endsOn ?? sub.ends_on ?? ""} onChange={e => setEndsOn(e.target.value)} style={{ maxWidth: 180 }} />
                <button className="btn btn-sm btn-ghost" disabled={busy || endsOn === null || !!endsOnError}
                  onClick={() => run(() => platformAdminApi.post(API.platformAdmin.saas.period(customerId), { ends_on: endsOn || null }), "Period updated.")}>Save</button>
                <FieldError msg={endsOnError} />
                <span style={{ flex: 1 }} />
                <button className={`btn btn-sm ${sub.status === "active" ? "btn-ghost" : "btn-filled"}`} disabled={busy}
                  onClick={() => run(() => platformAdminApi.post(API.platformAdmin.saas.status(customerId), { active: sub.status !== "active" }),
                    sub.status === "active" ? "Subscription deactivated." : "Subscription activated.")}>
                  {sub.status === "active" ? "Deactivate subscription" : "Activate subscription"}
                </button>
              </div>
              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                Deactivation blocks the company only when subscription enforcement is switched on (SUBSCRIPTION_ENFORCEMENT=on).
              </div>
            </>
          )}

          {data.history.length > 0 && (
            <div>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>History</div>
              <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
                <thead><tr><th>When</th><th>Event</th><th>Plan</th><th>By</th><th>Details</th></tr></thead>
                <tbody>
                  {data.history.map(h => (
                    <tr key={h.id}>
                      <td>{new Date(h.created_at).toLocaleString("en-IN")}</td>
                      <td>{EVENT_LABEL[h.event] ?? h.event}</td>
                      <td>{planChange(h)}</td>
                      <td>{h.admin_name ?? "System"}</td>
                      <td>{h.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
