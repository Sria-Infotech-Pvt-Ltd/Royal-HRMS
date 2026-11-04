"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { SaasFeature, SubscriptionPlan } from "@/types/platformAdmin";
import SaasTabs, { apiMessage, fmtMoney } from "../_components/SaasTabs";
import PlanEditorModal from "../_components/PlanEditorModal";

const STATUS_BADGE: Record<string, string> = { active: "badge-success", draft: "badge-neutral", inactive: "badge-neutral" };

export default function PlansPage() {
  const { data: plans, loading, error, refetch } = useFetch<SubscriptionPlan[]>(API.platformAdmin.saas.plans, platformAdminApi);
  const { data: catalogue } = useFetch<SaasFeature[]>(API.platformAdmin.saas.features, platformAdminApi);
  const [editing, setEditing] = useState<SubscriptionPlan | null | "new">(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function quick(plan: SubscriptionPlan, body: Partial<SubscriptionPlan>, done: string) {
    setBusy(plan.id);
    setMsg(null);
    try {
      await platformAdminApi.patch(API.platformAdmin.saas.plan(plan.id), body);
      setMsg({ ok: true, text: done });
      refetch();
    } catch (e) {
      setMsg({ ok: false, text: apiMessage(e, "Could not update the plan.") });
    } finally {
      setBusy(null);
    }
  }

  const list = plans ?? [];
  const matrixPlans = list.filter(p => !p.is_legacy);
  const matrixFeatures = (catalogue ?? []).filter(f => f.kind !== "core");

  return (
    <div className="saas-page">
      <SaasTabs title="Subscription Plans" sub="Create plans, set pricing and choose the modules each plan includes"
        actions={<button className="btn btn-filled" onClick={() => setEditing("new")} disabled={!catalogue}><i className="ti ti-plus" /> New plan</button>} />
      {msg && <div className={`alert mb-16 ${msg.ok ? "alert-success" : "alert-error"}`}>{msg.text}</div>}
      {error && <div className="alert alert-error mb-16">{error}</div>}

      <div className="card mb-24">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Plan</th><th>Price / employee / month</th><th>GST</th><th>Modules</th><th>Status</th><th>Customers</th><th /></tr>
            </thead>
            <tbody>
              {loading && list.length === 0 && <tr><td colSpan={7}>Loading…</td></tr>}
              {list.map(p => (
                <tr key={p.id}>
                  <td><strong>{p.name}</strong> <span style={{ color: "var(--on-variant)", fontSize: 12 }}>({p.code})</span>
                    {p.is_legacy && <span className="badge badge-neutral" style={{ marginLeft: 6 }}>Legacy</span>}</td>
                  <td>{fmtMoney(p.price_per_employee, p.currency)}</td>
                  <td>{Number(p.gst_rate)}% {p.gst_inclusive ? "incl." : "extra"}</td>
                  <td style={{ maxWidth: 280, fontSize: 12 }}>{p.modules.length ? p.modules.join(", ") : "core only"}</td>
                  <td>
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 4 }}>
                      <span className={`badge ${STATUS_BADGE[p.status]}`} style={{ textTransform: "capitalize" }}>{p.status}</span>
                      {p.is_public && <span className="badge badge-info">Published</span>}
                    </div>
                  </td>
                  <td>{p.subscriber_count}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 6, whiteSpace: "nowrap" }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => setEditing(p)}><i className="ti ti-edit" /> Edit</button>
                      {!p.is_legacy && (p.status === "active" ? (
                        <>
                          <button className="btn btn-ghost btn-sm" disabled={busy === p.id}
                            onClick={() => quick(p, { is_public: !p.is_public }, p.is_public ? "Plan unpublished." : "Plan published.")}>
                            {p.is_public ? "Unpublish" : "Publish"}
                          </button>
                          <button className="btn btn-ghost btn-sm" disabled={busy === p.id}
                            onClick={() => quick(p, { status: "inactive", is_public: false }, "Plan deactivated.")}>Deactivate</button>
                        </>
                      ) : (
                        <button className="btn btn-ghost btn-sm" disabled={busy === p.id}
                          onClick={() => quick(p, { status: "active" }, "Plan activated.")}>Activate</button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {matrixPlans.length > 0 && matrixFeatures.length > 0 && (
        <div className="card">
          <div style={{ padding: "14px 16px", fontWeight: 600 }}>Module matrix</div>
          <div className="table-wrap">
            <table style={{ fontSize: 12.5 }}>
              <thead><tr><th>Feature / module</th>{matrixPlans.map(p => <th key={p.id} style={{ textAlign: "center" }}>{p.name}</th>)}</tr></thead>
              <tbody>
                {matrixFeatures.map(f => (
                  <tr key={f.key}>
                    <td>{f.label}{f.kind === "coming_soon" && <span className="badge badge-neutral" style={{ marginLeft: 6 }}>Coming soon</span>}</td>
                    {matrixPlans.map(p => {
                      const on = p.features.includes(f.key) || p.modules.includes(f.key);
                      return <td key={p.id} style={{ textAlign: "center", color: on ? "var(--success)" : "var(--outline)" }}>
                        {f.kind === "coming_soon" ? "—" : on ? <i className="ti ti-check" /> : <i className="ti ti-minus" />}
                      </td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ padding: "8px 16px 14px", fontSize: 12, color: "var(--on-variant)" }}>
            Core HR (employees, self-service, onboarding, approvals, roles) is included in every plan. Edit a plan to change its modules.
          </div>
        </div>
      )}

      {editing && catalogue && (
        <PlanEditorModal plan={editing === "new" ? null : editing} catalogue={catalogue}
          onClose={() => setEditing(null)} onSaved={() => { setMsg({ ok: true, text: "Plan saved." }); refetch(); }} />
      )}
    </div>
  );
}
