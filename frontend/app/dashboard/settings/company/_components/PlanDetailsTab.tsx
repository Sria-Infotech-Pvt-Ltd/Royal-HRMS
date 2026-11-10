"use client";

// Company Settings → Plan Details (settings.edit only). Read-only view of what
// this company purchased, which modules are included / enabled, how other
// public plans compare, and its payment history. Every figure and state comes
// from GET /settings/company/plan/ (backend apps/tenants/customer_plan.py);
// nothing here changes the plan, modules or payments.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { formatMoney } from "@/lib/currency";
import {
  ACCESS_LABEL, PAYMENT_LABEL, SOURCE_LABEL, comparisonRows, enabledOutsidePlan, moduleLabels, moduleSummary,
  periodLabel, sourceNote,
} from "@/lib/planDetails";
import type { PlanDetails, PlanModuleRow } from "@/types/planDetails";

const fmtDate = (iso: string | null) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";

const PAYMENT_BADGE: Record<string, string> = {
  paid: "badge-success", waived: "badge-neutral", partially_paid: "badge-warn", pending: "badge-warn", failed: "badge-error",
};
const ACTIVATION: Record<string, { label: string; cls: string }> = {
  active:           { label: "Modules active", cls: "badge-success" },
  awaiting_payment: { label: "Activates when payment is confirmed", cls: "badge-warn" },
  setting_up:       { label: "Being set up", cls: "badge-warn" },
};

function Tile({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div style={{ background: "var(--bg-low)", borderRadius: 8, padding: "10px 12px" }}>
      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{label}</div>
      <div style={{ fontWeight: 700, fontSize: 16, color: tone }}>{value}</div>
    </div>
  );
}

function SourceBadge({ row }: { row: PlanModuleRow }) {
  const cls = row.source === "not_included" ? "badge-neutral" : row.source === "removed" ? "badge-error"
    : row.source === "added" ? "badge-info" : "badge-success";
  return <span className={`badge ${cls}`}>{SOURCE_LABEL[row.source]}</span>;
}

function AccessBadge({ row, hasPlan }: { row: PlanModuleRow; hasPlan: boolean }) {
  if (enabledOutsidePlan(row, hasPlan)) return <span className="badge badge-success">Enabled (not part of your plan)</span>;
  const cls = row.access === "enabled" ? "badge-success" : row.access === "pending" ? "badge-warn" : "badge-neutral";
  return <span className={`badge ${cls}`}>{ACCESS_LABEL[row.access]}</span>;
}

function Chips({ items }: { items: { key: string; label: string; description: string }[] }) {
  if (!items.length) return <span style={{ color: "var(--on-variant)" }}>—</span>;
  return (
    <span style={{ display: "inline-flex", flexWrap: "wrap", gap: 6 }}>
      {items.map(i => <span key={i.key} className="badge badge-neutral" title={i.description}>{i.label}</span>)}
    </span>
  );
}

export default function PlanDetailsTab() {
  const { data, loading, error } = useFetch<PlanDetails>(API.settings.companyPlan);

  if (loading) {
    return <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>Loading plan details…</div>;
  }
  if (error || !data) {
    return <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{error ?? "Could not load plan details."}</div></div>;
  }

  const cur = data.current;
  const money = (v: string | null, currency = cur?.currency ?? "INR") => (v === null ? "—" : formatMoney(v, currency));
  const summary = moduleSummary(data.modules);
  const rows = [...data.modules].sort((a, b) => Number(b.included) - Number(a.included) || a.label.localeCompare(b.label));
  const comparison = comparisonRows(data);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, paddingBottom: 32 }}>
      {/* ── Current plan ── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-certificate" /> Your plan</div>
        </div>
        <div style={{ padding: "4px 20px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
          {!cur ? (
            <div className="alert alert-info">
              <i className="ti ti-info-circle" />
              <div>No subscription plan is assigned to your company yet. The modules below are what your users can use today.
                Contact your account manager to choose a plan.</div>
            </div>
          ) : (
            <>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 22, fontWeight: 800 }}>{cur.plan_name}</span>
                <span className={`badge ${cur.status === "active" ? "badge-success" : "badge-neutral"}`}>
                  {cur.status === "active" ? "Active" : "Inactive"}
                </span>
                <span className={`badge ${PAYMENT_BADGE[cur.payment_status] ?? "badge-neutral"}`}>{PAYMENT_LABEL[cur.payment_status]}</span>
                <span className={`badge ${ACTIVATION[cur.activation].cls}`}>{ACTIVATION[cur.activation].label}</span>
              </div>
              {cur.description && <div style={{ color: "var(--on-variant)" }}>{cur.description}</div>}
              <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", fontSize: 13 }}>
                <div><div style={{ fontSize: 11, color: "var(--on-variant)" }}>Billing cycle</div>{periodLabel(cur.billing_period)}</div>
                <div><div style={{ fontSize: 11, color: "var(--on-variant)" }}>Start date</div>{fmtDate(cur.starts_on)}</div>
                <div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>End date</div>
                  {cur.ends_on ? fmtDate(cur.ends_on) : "No end date"}
                  {cur.days_left !== null && <span style={{ color: "var(--on-variant)" }}> · {cur.days_left} day{cur.days_left === 1 ? "" : "s"} left</span>}
                </div>
                <div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Price</div>
                  {money(cur.price_per_employee)} / employee / month
                  {cur.gst_inclusive ? " (GST incl.)" : ` + ${Number(cur.gst_rate)}% GST`}
                </div>
                {cur.employee_count !== null && (
                  <div><div style={{ fontSize: 11, color: "var(--on-variant)" }}>Employees</div>{cur.employee_count}</div>
                )}
              </div>
              {cur.period_ended && (
                <div className="alert alert-warn">
                  <i className="ti ti-calendar-exclamation" />
                  <div>The subscription period ended on {fmtDate(cur.ends_on)}. Your access continues — contact your account manager to renew.</div>
                </div>
              )}
              <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
                <Tile label="Total plan amount" value={cur.total_amount !== null ? money(cur.total_amount) : "Not set"} />
                <Tile label="Amount paid" value={money(cur.amount_paid)} />
                {Number(cur.amount_pending_confirmation) > 0 && <Tile label="Awaiting confirmation" value={money(cur.amount_pending_confirmation)} />}
                <Tile label="Outstanding" value={cur.payment_status === "waived" ? "Waived" : money(cur.amount_outstanding)}
                  tone={Number(cur.amount_outstanding) > 0 ? "var(--warn)" : undefined} />
              </div>
              <div style={{ fontSize: 13 }}><strong>Plan features:</strong> <Chips items={cur.features} /></div>
            </>
          )}
        </div>
      </div>

      {/* ── Modules ── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-apps" /> Modules</div>
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
            {summary.included} included · {summary.enabled} enabled{summary.pending ? ` · ${summary.pending} activate after payment` : ""} · {summary.notIncluded} not included
          </span>
        </div>
        <div className="table-wrap">
          <table className="data-table" style={{ width: "100%", fontSize: 13 }}>
            <thead><tr><th>Module</th><th>Description</th><th>In your plan</th><th>Access</th></tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.key} style={{ opacity: !r.included && !r.enabled ? 0.65 : 1 }}>
                  <td style={{ fontWeight: 600 }}>{r.label}<div style={{ fontSize: 11, color: "var(--on-variant)", fontWeight: 400 }}>{r.category}</div></td>
                  <td style={{ color: "var(--on-variant)" }}>{r.description}</td>
                  <td>
                    {data.has_plan ? <SourceBadge row={r} /> : <span className="badge badge-neutral">No plan</span>}
                    {sourceNote(r) && <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 3 }}>{sourceNote(r)}</div>}
                  </td>
                  <td><AccessBadge row={r} hasPlan={data.has_plan} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ padding: "12px 20px", display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
          <div><strong>Always included:</strong> <Chips items={data.always_included} /></div>
          <div><strong>Coming soon:</strong> <Chips items={data.coming_soon} /></div>
        </div>
      </div>

      {/* ── Other plans ── */}
      {data.other_plans.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="ti ti-arrows-diff" /> Other plans</div>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>For information — to change plans, contact your account manager.</span>
          </div>
          <div style={{ padding: "4px 20px 16px", display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
            {data.other_plans.map(p => (
              <div key={p.code} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: 14, display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
                <div style={{ fontSize: 16, fontWeight: 700 }}>{p.name}</div>
                {p.description && <div style={{ color: "var(--on-variant)" }}>{p.description}</div>}
                <div>
                  <strong>{formatMoney(p.price_per_employee, p.currency)}</strong> / employee / month
                  {p.gst_inclusive ? " (GST incl.)" : ` + ${Number(p.gst_rate)}% GST`}
                  <span style={{ color: "var(--on-variant)" }}> · billed {p.billing_periods.map(periodLabel).join(" or ").toLowerCase()}</span>
                </div>
                {p.estimates.length > 0 && (
                  <div style={{ background: "var(--bg-low)", borderRadius: 8, padding: "6px 10px" }}>
                    For your {p.estimate_employee_count} employees:{" "}
                    {p.estimates.map(e => `${formatMoney(e.total, p.currency)} / ${e.billing_period === "yearly" ? "year" : "month"}`).join(" · ")}
                    {" "}(incl. GST)
                    {!p.fits_employee_count && (
                      <div style={{ color: "var(--warn)", fontSize: 12 }}>
                        This plan is for {p.min_employees ?? 1}–{p.max_employees ?? "any number of"} employees.
                      </div>
                    )}
                  </div>
                )}
                <div>
                  <strong style={{ color: "var(--success)" }}>You would also get:</strong>{" "}
                  {p.additional_modules.length ? moduleLabels(data, p.additional_modules).join(", ") : "no additional modules"}
                </div>
                {p.modules_not_included.length > 0 && (
                  <div style={{ color: "var(--on-variant)" }}>
                    <strong>Not in this plan:</strong> {moduleLabels(data, p.modules_not_included).join(", ")}
                  </div>
                )}
                {p.features.length > 0 && <div><strong>Features:</strong> <Chips items={p.features} /></div>}
              </div>
            ))}
          </div>
          {comparison.length > 0 && (
            <div className="table-wrap" style={{ padding: "0 20px 20px" }}>
              <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
                <thead>
                  <tr>
                    <th>Module</th>
                    <th>{cur ? `${cur.plan_name} (current)` : "Today"}</th>
                    {data.other_plans.map(p => <th key={p.code}>{p.name}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {comparison.map(r => (
                    <tr key={r.key}>
                      <td>{r.label}</td>
                      <td>{r.current ? <i className="ti ti-check" style={{ color: "var(--success)" }} /> : "—"}</td>
                      {data.other_plans.map(p => (
                        <td key={p.code}>
                          {r.plans[p.code]
                            ? <i className="ti ti-check" style={{ color: r.current ? "var(--success)" : "var(--primary)", fontWeight: 700 }}
                                title={r.current ? "Included" : "Additional module"} />
                            : "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Payment history ── */}
      {cur && (
        <div className="card">
          <div className="card-header"><div className="card-title"><i className="ti ti-receipt" /> Payment history</div></div>
          {data.payments.length === 0 ? (
            <div style={{ padding: "4px 20px 20px", color: "var(--on-variant)", fontSize: 13 }}>
              {cur.payment_status === "waived" ? "Payment is waived for this subscription." : "No payments recorded yet."}
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data-table" style={{ width: "100%", fontSize: 13 }}>
                <thead><tr><th>Date</th><th>Amount</th><th>Method</th><th>Reference</th><th>Status</th></tr></thead>
                <tbody>
                  {data.payments.map((p, i) => (
                    <tr key={`${p.paid_on}-${i}`}>
                      <td>{fmtDate(p.paid_on)}</td>
                      <td>{formatMoney(p.amount, p.currency)}</td>
                      <td>{p.method}</td>
                      <td>{p.reference || "—"}</td>
                      <td>
                        <span className={`badge ${p.status === "confirmed" ? "badge-success" : "badge-warn"}`}>
                          {p.status === "confirmed" ? "Confirmed" : "Awaiting confirmation"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
