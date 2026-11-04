"use client";

import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { SaasDashboard } from "@/types/platformAdmin";
import SaasTabs from "./_components/SaasTabs";

function Stat({ label, value, icon, tone }: { label: string; value: number | string; icon: string; tone?: string }) {
  return (
    <div className="card" style={{ padding: 16, display: "flex", gap: 12, alignItems: "center" }}>
      <i className={`ti ${icon}`} style={{ fontSize: 26, color: tone ?? "var(--primary)" }} />
      <div>
        <div style={{ fontSize: 22, fontWeight: 800, color: "var(--on-bg)" }}>{value}</div>
        <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{label}</div>
      </div>
    </div>
  );
}

export default function SaasDashboardPage() {
  const { data, loading, error } = useFetch<SaasDashboard>(API.platformAdmin.saas.dashboard, platformAdminApi);

  return (
    <div className="saas-page">
      <SaasTabs title="SaaS & Subscriptions" sub="Plans, customer subscriptions and module access" />
      {error && <div className="alert alert-error mb-16">{error}</div>}
      {loading && !data && <div style={{ color: "var(--on-variant)" }}>Loading…</div>}
      {data && (
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
            <Stat label={`Plans (${data.plans_active} active, ${data.plans_public} published)`} value={data.plans_total} icon="ti-stack-2" />
            <Stat label="Customers" value={data.customers_total} icon="ti-building" />
            <Stat label="Active subscriptions" value={data.subscriptions_active} icon="ti-circle-check" tone="var(--success)" />
            <Stat label="Inactive subscriptions" value={data.subscriptions_inactive} icon="ti-circle-minus" tone="var(--on-variant)" />
            <Stat label="Customers without a subscription" value={data.customers_without_subscription} icon="ti-alert-triangle" tone="#9a6700" />
            <Stat label="Failed provisioning" value={data.provisioning_failed} icon="ti-alert-circle" tone="var(--error)" />
            <Stat label="Registrations waiting for approval" value={data.registrations_pending_approval} icon="ti-user-check" tone="var(--primary)" />
            <Stat label="Registrations waiting for payment" value={data.registrations_awaiting_payment} icon="ti-clock" tone="var(--on-variant)" />
            <Stat label={`Paid registrations (${data.registrations_rejected} rejected)`} value={data.registrations_paid} icon="ti-receipt" tone="var(--success)" />
          </div>
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 10 }}>Customers per plan</div>
              {data.by_plan.length === 0 ? <div style={{ fontSize: 13, color: "var(--on-variant)" }}>No subscriptions yet.</div> : (
                <table className="data-table" style={{ width: "100%", fontSize: 13 }}>
                  <tbody>
                    {data.by_plan.map(p => <tr key={p.plan_name}><td>{p.plan_name}</td><td style={{ textAlign: "right" }}>{p.customers}</td></tr>)}
                  </tbody>
                </table>
              )}
            </div>
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 10 }}>By source</div>
              <table className="data-table" style={{ width: "100%", fontSize: 13 }}>
                <tbody>
                  {(["manual", "website", "legacy"] as const).map(s => (
                    <tr key={s}><td style={{ textTransform: "capitalize" }}>{s}</td><td style={{ textAlign: "right" }}>{data.by_source[s] ?? 0}</td></tr>
                  ))}
                </tbody>
              </table>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 10 }}>
                Online payment is not connected yet — website registrations stay &ldquo;waiting for payment&rdquo; and cannot be approved until it is.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
