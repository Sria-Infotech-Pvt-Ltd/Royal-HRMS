"use client";

// Create / edit a subscription plan, including its feature & module switches.
// Core features are always on; "Coming soon" features cannot be included.
// Dependencies (e.g. Payroll needs Attendance + Leave) are switched on by the
// server and shown here. Saving never changes existing subscriptions.

import { useMemo, useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { CURRENCIES, currencyLabel } from "@/lib/currency";
import FieldError from "@/components/FieldError";
import * as v from "@/lib/saasValidation";
import type { PlanStatus, SaasFeature, SubscriptionPlan } from "@/types/platformAdmin";
import { apiMessage } from "./SaasTabs";

interface Form {
  code: string;
  name: string;
  description: string;
  price_per_employee: string;
  currency: string;
  billing_periods: ("monthly" | "yearly")[];
  gst_rate: string;
  gst_inclusive: boolean;
  min_employees: string;
  max_employees: string;
  status: PlanStatus;
  is_public: boolean;
  display_order: string;
  features: string[];
}

function toForm(plan: SubscriptionPlan | null): Form {
  return {
    code: plan?.code ?? "", name: plan?.name ?? "", description: plan?.description ?? "",
    price_per_employee: plan?.price_per_employee ?? "0", currency: plan?.currency ?? "INR",
    billing_periods: plan?.billing_periods ?? ["monthly"], gst_rate: plan?.gst_rate ?? "18",
    gst_inclusive: plan?.gst_inclusive ?? false,
    min_employees: plan?.min_employees != null ? String(plan.min_employees) : "",
    max_employees: plan?.max_employees != null ? String(plan.max_employees) : "",
    status: plan?.status ?? "draft", is_public: plan?.is_public ?? false,
    display_order: String(plan?.display_order ?? 0), features: plan?.features ?? [],
  };
}

/** Module keys the selected features switch on, including dependencies. */
export function modulesFor(features: string[], catalogue: SaasFeature[]): string[] {
  const byKey = new Map(catalogue.map(f => [f.key, f]));
  const out = new Set(features.filter(k => byKey.get(k)?.kind === "module"));
  let changed = true;
  while (changed) {
    changed = false;
    for (const k of Array.from(out)) {
      for (const dep of byKey.get(k)?.depends_on ?? []) {
        if (!out.has(dep)) { out.add(dep); changed = true; }
      }
    }
  }
  return Array.from(out).sort();
}

export default function PlanEditorModal({ plan, catalogue, onClose, onSaved }: {
  plan: SubscriptionPlan | null;
  catalogue: SaasFeature[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<Form>(toForm(plan));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [errors, setErrors] = useState<v.Errors>({});
  const legacy = plan?.is_legacy ?? false;
  const set = <K extends keyof Form>(k: K, val: Form[K]) => {
    setForm(f => ({ ...f, [k]: val }));
    setErrors(e => { const rest = { ...e }; delete rest[k]; return rest; });
  };

  function validate(): v.Errors {
    const codeUnchanged = !!plan && plan.code.toLowerCase() === form.code.trim().toLowerCase();
    const min = form.min_employees.trim(), max = form.max_employees.trim();
    const bothWhole = /^\d+$/.test(min) && /^\d+$/.test(max);
    return v.collect({
      name: v.businessName(form.name, "Plan name") ?? v.maxLength(form.name, 100),
      code: v.required(form.code, "Plan code") ?? (codeUnchanged ? null : v.planCode(form.code)),
      display_order: v.wholeNumber(form.display_order, { min: 0, max: 32767, what: "Display order" }),
      description: v.maxLength(form.description, 1000),
      price_per_employee: v.decimal(form.price_per_employee, { max: 99999999.99, what: "Price" }),
      gst_rate: v.decimal(form.gst_rate, { max: 100, what: "GST" }),
      billing_periods: form.billing_periods.length ? null : "Choose at least one billing period.",
      min_employees: v.wholeNumber(min, { what: "Minimum employees" }),
      max_employees: v.wholeNumber(max, { what: "Maximum employees" })
        ?? (bothWhole && Number(min) > Number(max) ? "Maximum must be at least the minimum." : null),
      currency: CURRENCIES.some(c => c.code === form.currency) || plan?.currency === form.currency
        ? null : "Choose a supported currency.",
    });
  }

  const modules = useMemo(() => modulesFor(form.features, catalogue), [form.features, catalogue]);
  const categories = useMemo(() => {
    const map = new Map<string, SaasFeature[]>();
    catalogue.forEach(f => map.set(f.category, [...(map.get(f.category) ?? []), f]));
    return Array.from(map.entries());
  }, [catalogue]);

  function toggle(key: string) {
    set("features", form.features.includes(key) ? form.features.filter(k => k !== key) : [...form.features, key]);
  }

  async function save() {
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length) { setErr("Please correct the highlighted fields."); return; }
    setSaving(true);
    setErr(null);
    const body: Record<string, unknown> = {
      code: form.code, name: form.name, description: form.description,
      price_per_employee: form.price_per_employee || "0", currency: form.currency,
      billing_periods: form.billing_periods, gst_rate: form.gst_rate || "0", gst_inclusive: form.gst_inclusive,
      min_employees: form.min_employees ? Number(form.min_employees) : null,
      max_employees: form.max_employees ? Number(form.max_employees) : null,
      display_order: Number(form.display_order || 0),
    };
    if (!legacy) Object.assign(body, { status: form.status, is_public: form.is_public, features: form.features });
    try {
      if (plan) await platformAdminApi.patch(API.platformAdmin.saas.plan(plan.id), body);
      else await platformAdminApi.post(API.platformAdmin.saas.plans, body);
      onSaved();
      onClose();
    } catch (e) {
      setErrors(v.apiFieldErrors(e));
      setErr(apiMessage(e, "Could not save the plan."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={plan ? `Edit plan — ${plan.name}` : "New subscription plan"}
      onClose={onClose}
      closeDisabled={saving}
      size="xl"
      footer={
        <>
          {plan && plan.subscriber_count > 0 && (
            <span style={{ marginRight: "auto", fontSize: 12, color: "var(--on-variant)" }}>
              {plan.subscriber_count} customer(s) on this plan keep their current terms — changes apply to new assignments.
            </span>
          )}
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-filled" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save plan"}
          </button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 18, fontSize: 13 }}>
        {err && <div className="alert alert-error">{err}</div>}
        {legacy && <div className="alert alert-info">The legacy plan keeps existing companies&apos; modules; its features and status are fixed.</div>}

        <div className="form-row cols-3">
          <div className="field-group">
            <label className="field-label">Plan name *</label>
            <input className="field-input" value={form.name} onChange={e => set("name", e.target.value)} maxLength={100} />
            <FieldError msg={errors.name} />
          </div>
          <div className="field-group">
            <label className="field-label">Plan code *</label>
            <input className="field-input" value={form.code} onChange={e => set("code", e.target.value.toLowerCase())}
              maxLength={40} placeholder="e.g. growth" disabled={!!plan && plan.subscriber_count > 0} />
            <FieldError msg={errors.code} />
          </div>
          <div className="field-group">
            <label className="field-label">Display order</label>
            <input className="field-input" type="number" min={0} max={32767} step={1} inputMode="numeric" value={form.display_order}
              onChange={e => set("display_order", e.target.value)} />
            <FieldError msg={errors.display_order} />
          </div>
        </div>
        <div className="field-group">
          <label className="field-label">Description</label>
          <textarea className="field-input" rows={2} maxLength={1000} value={form.description} onChange={e => set("description", e.target.value)} />
          <FieldError msg={errors.description} />
        </div>

        <div className="form-row cols-3">
          <div className="field-group">
            <label className="field-label">Price per employee / month ({CURRENCIES.find(c => c.code === form.currency)?.symbol ?? form.currency})</label>
            <input className="field-input" type="number" min={0} step="0.01" inputMode="decimal" value={form.price_per_employee}
              onChange={e => set("price_per_employee", e.target.value)} />
            <FieldError msg={errors.price_per_employee} />
          </div>
          <div className="field-group">
            <label className="field-label">Currency</label>
            <select className="field-input" value={form.currency} onChange={e => set("currency", e.target.value)}>
              {CURRENCIES.map(c => <option key={c.code} value={c.code}>{currencyLabel(c)}</option>)}
              {!CURRENCIES.some(c => c.code === form.currency) && <option value={form.currency}>{form.currency}</option>}
            </select>
            <span style={{ fontSize: 11, color: "var(--on-variant)" }}>Prices are entered in this currency — no conversion.</span>
            <FieldError msg={errors.currency} />
          </div>
          <div className="field-group">
            <label className="field-label">GST</label>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input className="field-input" type="number" min={0} max={100} step="0.01" inputMode="decimal" value={form.gst_rate}
                onChange={e => set("gst_rate", e.target.value)} style={{ width: 90 }} />
              <span>%</span>
              <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <input type="checkbox" checked={form.gst_inclusive} onChange={e => set("gst_inclusive", e.target.checked)} />
                Price includes GST
              </label>
            </div>
            <FieldError msg={errors.gst_rate} />
          </div>
        </div>

        <div className="form-row cols-3">
          <div className="field-group">
            <label className="field-label">Billing periods</label>
            <div style={{ display: "flex", gap: 14, paddingTop: 6 }}>
              {(["monthly", "yearly"] as const).map(p => (
                <label key={p} style={{ display: "flex", gap: 6, alignItems: "center", textTransform: "capitalize" }}>
                  <input type="checkbox" checked={form.billing_periods.includes(p)}
                    onChange={e => set("billing_periods", e.target.checked ? [...form.billing_periods, p] : form.billing_periods.filter(x => x !== p))} />
                  {p}
                </label>
              ))}
            </div>
            <FieldError msg={errors.billing_periods} />
          </div>
          <div className="field-group">
            <label className="field-label">Employees (min – max)</label>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input className="field-input" type="number" min={1} max={v.MAX_EMPLOYEES} step={1} inputMode="numeric" placeholder="Min"
                value={form.min_employees} onChange={e => set("min_employees", e.target.value)} />
              <span>–</span>
              <input className="field-input" type="number" min={1} max={v.MAX_EMPLOYEES} step={1} inputMode="numeric" placeholder="No limit"
                value={form.max_employees} onChange={e => set("max_employees", e.target.value)} />
            </div>
            <FieldError msg={errors.min_employees ?? errors.max_employees} />
          </div>
          {!legacy && (
            <div className="field-group">
              <label className="field-label">Status</label>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <select className="field-input" value={form.status}
                  onChange={e => { const s = e.target.value as PlanStatus; setForm(f => ({ ...f, status: s, is_public: s === "active" ? f.is_public : false })); }}>
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
                <label style={{ display: "flex", gap: 6, alignItems: "center", whiteSpace: "nowrap", opacity: form.status === "active" ? 1 : 0.5 }}>
                  <input type="checkbox" checked={form.is_public} disabled={form.status !== "active"}
                    onChange={e => set("is_public", e.target.checked)} />
                  Published
                </label>
              </div>
            </div>
          )}
        </div>

        <div>
          <div className="field-label mb-2">Features & modules</div>
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
            {categories.map(([category, feats]) => (
              <div key={category} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>{category}</div>
                {feats.map(f => {
                  const core = f.kind === "core";
                  const soon = f.kind === "coming_soon";
                  const on = core || form.features.includes(f.key);
                  const viaDep = f.kind === "module" && !on && modules.includes(f.key);
                  return (
                    <label key={f.key} style={{ display: "flex", gap: 8, alignItems: "flex-start", padding: "4px 0",
                      opacity: soon ? 0.55 : 1, cursor: core || soon || legacy ? "default" : "pointer" }}>
                      <input type="checkbox" checked={on || viaDep} disabled={core || soon || legacy || viaDep}
                        onChange={() => toggle(f.key)} />
                      <span>
                        {f.label}
                        {core && <span className="badge badge-neutral" style={{ marginLeft: 6 }}>Always included</span>}
                        {soon && <span className="badge badge-neutral" style={{ marginLeft: 6 }}>Coming soon</span>}
                        {f.kind === "display" && <span style={{ marginLeft: 6, fontSize: 11, color: "var(--on-variant)" }}>(shown on plan)</span>}
                        {viaDep && <span style={{ marginLeft: 6, fontSize: 11, color: "var(--on-variant)" }}>(required by another module)</span>}
                        {f.description && <span style={{ display: "block", fontSize: 11, color: "var(--on-variant)" }}>{f.description}</span>}
                      </span>
                    </label>
                  );
                })}
              </div>
            ))}
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 8 }}>
            Modules switched on: {modules.length ? modules.join(", ") : "none (core only)"}
          </div>
          <FieldError msg={errors.features} />
        </div>
      </div>
    </Modal>
  );
}
