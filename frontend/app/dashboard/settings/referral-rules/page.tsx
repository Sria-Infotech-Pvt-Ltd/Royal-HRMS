"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ReferralRule {
  id:        number;
  icon:      string;
  title:     string;
  body:      string;
  order:     number;
  is_active: boolean;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const ICON_OPTIONS = [
  { value: "ti-users",          label: "Users"               },
  { value: "ti-currency-rupee", label: "Currency / Bonus"    },
  { value: "ti-user-cancel",    label: "User Restriction"    },
  { value: "ti-calendar-off",   label: "Calendar / Dates"    },
  { value: "ti-list-numbers",   label: "Numbered List"       },
  { value: "ti-receipt-tax",    label: "Tax / Receipt"       },
  { value: "ti-shield-check",   label: "Shield / Security"   },
  { value: "ti-award",          label: "Award / Achievement" },
  { value: "ti-gift",           label: "Gift / Reward"       },
  { value: "ti-info-circle",    label: "Information"         },
  { value: "ti-clock",          label: "Time / Duration"     },
  { value: "ti-building",       label: "Company / Branch"    },
  { value: "ti-star",           label: "Star"                },
  { value: "ti-check",          label: "Check / Tick"        },
];

const EMPTY_FORM = { icon: "ti-info-circle", title: "", body: "", order: 1, is_active: true };

// ── Inline form (shared by Add and Edit) ──────────────────────────────────────

function RuleForm({
  form, setField, saving, error,
  onSave, onCancel,
}: {
  form: typeof EMPTY_FORM;
  setField: <K extends keyof typeof EMPTY_FORM>(k: K, v: typeof EMPTY_FORM[K]) => void;
  saving: boolean;
  error: string;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <div>
      {error && (
        <div className="alert alert-error" style={{ marginBottom: 14 }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "140px 1fr 80px", gap: "0 16px", marginBottom: 12 }}>
        {/* Icon picker */}
        <div className="field-group">
          <label className="field-label">Icon</label>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: "rgba(30,78,140,0.09)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <i className={`ti ${form.icon}`} style={{ fontSize: 16, color: "var(--primary)" }} />
            </div>
            <select className="field-input field-select" style={{ flex: 1 }}
              value={form.icon} onChange={e => setField("icon", e.target.value)} suppressHydrationWarning>
              {ICON_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        </div>

        {/* Title */}
        <div className="field-group">
          <label className="field-label">Rule Title <span style={{ color: "var(--error)" }}>*</span></label>
          <input className="field-input" placeholder="e.g. Eligibility"
            value={form.title} onChange={e => setField("title", e.target.value)}
            required suppressHydrationWarning />
        </div>

        {/* Order */}
        <div className="field-group">
          <label className="field-label">Order</label>
          <input type="number" className="field-input" min={1}
            value={form.order} onChange={e => setField("order", Number(e.target.value))}
            suppressHydrationWarning />
        </div>
      </div>

      {/* Body */}
      <div className="field-group" style={{ marginBottom: 14 }}>
        <label className="field-label">Description <span style={{ color: "var(--error)" }}>*</span></label>
        <textarea className="field-input" rows={2}
          placeholder="Explain this rule clearly so employees understand it…"
          value={form.body} onChange={e => setField("body", e.target.value)}
          suppressHydrationWarning style={{ resize: "vertical" }} />
      </div>

      {/* Active toggle */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, userSelect: "none" }}>
          <input type="checkbox" checked={form.is_active}
            onChange={e => setField("is_active", e.target.checked)} suppressHydrationWarning />
          Show this rule to employees
        </label>
      </div>

      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn btn-filled" onClick={onSave} disabled={saving} suppressHydrationWarning>
          {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : <><i className="ti ti-device-floppy" /> Save Rule</>}
        </button>
        <button className="btn btn-ghost" onClick={onCancel} suppressHydrationWarning>
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ReferralRulesSettingsPage() {
  const router = useRouter();

  const [editing,  setEditing]  = useState<number | "new" | null>(null);
  const [form,     setForm]     = useState<typeof EMPTY_FORM>(EMPTY_FORM);
  const [saving,   setSaving]   = useState(false);
  const [formErr,  setFormErr]  = useState("");
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const { data, loading, refetch } =
    useFetch<{ results: ReferralRule[] }>(API.referralRules.list);
  const rules = [...(data?.results ?? [])].sort((a, b) => a.order - b.order);

  function setField<K extends keyof typeof EMPTY_FORM>(key: K, value: typeof EMPTY_FORM[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  function startAdd() {
    setEditing("new");
    setForm({ ...EMPTY_FORM, order: rules.length + 1 });
    setFormErr("");
  }

  function startEdit(rule: ReferralRule) {
    setEditing(rule.id);
    setForm({ icon: rule.icon, title: rule.title, body: rule.body, order: rule.order, is_active: rule.is_active });
    setFormErr("");
  }

  async function handleSave() {
    if (!form.title.trim() || !form.body.trim()) {
      setFormErr("Title and description are required.");
      return;
    }
    setSaving(true);
    setFormErr("");
    try {
      if (editing === "new") {
        await clientApi.post(API.referralRules.create, form);
      } else {
        await clientApi.patch(API.referralRules.detail(editing as number), form);
      }
      setEditing(null);
      refetch();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })
          ?.response?.data?.message ?? "Failed to save rule.";
      setFormErr(msg);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    setConfirmDelete(null);
    try {
      await clientApi.delete(API.referralRules.detail(id));
      refetch();
    } catch { /* list will refresh */ }
  }

  const isBusy = editing !== null;

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Referral Rules</div>
          <div className="page-sub">Rules shown to employees on the Referral page. Changes take effect immediately.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.back()} suppressHydrationWarning>
            <i className="ti ti-arrow-left" /> Back
          </button>
          <button className="btn btn-filled" onClick={startAdd} disabled={isBusy} suppressHydrationWarning>
            <i className="ti ti-plus" /> Add Rule
          </button>
        </div>
      </div>

      {/* Add new rule card */}
      {editing === "new" && (
        <div className="card" style={{ marginBottom: 20, borderColor: "var(--primary)", borderWidth: 2 }}>
          <div className="card-header">
            <span className="card-title" style={{ color: "var(--primary)" }}>
              <i className="ti ti-plus" /> New Rule
            </span>
          </div>
          <div style={{ padding: "0 20px 20px" }}>
            <RuleForm form={form} setField={setField} saving={saving} error={formErr}
              onSave={handleSave} onCancel={() => setEditing(null)} />
          </div>
        </div>
      )}

      {/* Rules list */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <i className="ti ti-list" /> Configured Rules ({rules.length})
          </span>
        </div>

        {loading ? (
          <div className="text-center py-10"><i className="ti ti-loader-2 spin text-3xl" /></div>
        ) : rules.length === 0 && editing !== "new" ? (
          <div className="empty-state">
            <i className="ti ti-file-text" />
            <h3>No rules configured</h3>
            <p>Click &ldquo;Add Rule&rdquo; to create the first referral rule.</p>
          </div>
        ) : (
          <div>
            {rules.map((rule, idx) => (
              <div key={rule.id}
                style={{ borderBottom: idx < rules.length - 1 ? "1px solid var(--outline-v)" : "none", padding: "18px 20px" }}>
                {editing === rule.id ? (
                  <RuleForm form={form} setField={setField} saving={saving} error={formErr}
                    onSave={handleSave} onCancel={() => setEditing(null)} />
                ) : (
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
                    {/* Icon */}
                    <div style={{ width: 40, height: 40, borderRadius: 10, background: rule.is_active ? "rgba(30,78,140,0.09)" : "var(--bg)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <i className={`ti ${rule.icon}`} style={{ fontSize: 18, color: rule.is_active ? "var(--primary)" : "var(--on-variant)" }} />
                    </div>

                    {/* Content */}
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 10, fontWeight: 700, color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.07em" }}>
                          Rule {rule.order}
                        </span>
                        <strong style={{ fontSize: 14, color: "var(--on-bg)" }}>{rule.title}</strong>
                        {!rule.is_active && (
                          <span className="badge badge-neutral" style={{ fontSize: 10 }}>Hidden</span>
                        )}
                      </div>
                      <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0, lineHeight: 1.6 }}>{rule.body}</p>
                    </div>

                    {/* Actions */}
                    <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => startEdit(rule)} disabled={isBusy} suppressHydrationWarning>
                        <i className="ti ti-pencil" /> Edit
                      </button>
                      {confirmDelete === rule.id ? (
                        <>
                          <button suppressHydrationWarning
                            style={{ background: "var(--error)", color: "#fff", border: "none", borderRadius: 8, padding: "6px 12px", cursor: "pointer", fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 5 }}
                            onClick={() => handleDelete(rule.id)}>
                            <i className="ti ti-check" /> Confirm
                          </button>
                          <button className="btn btn-ghost btn-sm" onClick={() => setConfirmDelete(null)} suppressHydrationWarning>
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }}
                          onClick={() => setConfirmDelete(rule.id)} disabled={isBusy} suppressHydrationWarning>
                          <i className="ti ti-trash" /> Delete
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
