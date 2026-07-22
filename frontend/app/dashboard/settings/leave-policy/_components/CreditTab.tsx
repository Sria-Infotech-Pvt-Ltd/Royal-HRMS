"use client";

import { useEffect, useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useFiscalYearConfig } from "@/lib/fiscalYear";
import { LEAVE_NAME_RE, sanitizeLeaveName } from "@/lib/leaveValidation";

// ─── Types ────────────────────────────────────────────────────────────────────

type AccrualFrequency = "monthly" | "quarterly" | "annually" | "on_joining";

interface CreditRule {
  id: number;
  leave_type: string;
  accrual_days: number;
  frequency: AccrualFrequency;
  max_balance: number;
  encashable: boolean;
  encash_limit: number;
  min_service_months: number;
  is_active: boolean;
}

const SEED: CreditRule[] = [
  { id: 1, leave_type: "Earned Leave",  accrual_days: 1.5, frequency: "monthly",  max_balance: 45, encashable: true,  encash_limit: 15, min_service_months: 6,  is_active: true  },
  { id: 2, leave_type: "Casual Leave",  accrual_days: 1,   frequency: "monthly",  max_balance: 12, encashable: false, encash_limit: 0,  min_service_months: 0,  is_active: true  },
  { id: 3, leave_type: "Sick Leave",    accrual_days: 0.5, frequency: "monthly",  max_balance: 6,  encashable: false, encash_limit: 0,  min_service_months: 0,  is_active: true  },
  { id: 4, leave_type: "Annual Leave",  accrual_days: 21,  frequency: "annually", max_balance: 21, encashable: true,  encash_limit: 10, min_service_months: 12, is_active: false },
];

const FREQ_LABELS: Record<AccrualFrequency, string> = {
  monthly: "Monthly", quarterly: "Quarterly", annually: "Annually", on_joining: "On Joining",
};

const BLANK: Omit<CreditRule, "id"> = {
  leave_type: "", accrual_days: 1, frequency: "monthly",
  max_balance: 12, encashable: false, encash_limit: 0,
  min_service_months: 0, is_active: true,
};

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function CreditTab() {
  const fy = useFiscalYearConfig();
  const [creditYear,  setCreditYear]  = useState<number>(fy.currentYear);
  const [yearEdited,  setYearEdited]  = useState(false);
  const [crediting,    setCrediting]    = useState(false);
  const [creditResult, setCreditResult] = useState<{ credited: number } | null>(null);
  const [creditError,  setCreditError]  = useState<string | null>(null);

  const [rules,   setRules]   = useState<CreditRule[]>(SEED);
  const [modal,   setModal]   = useState<"add" | "edit" | null>(null);
  const [editing, setEditing] = useState<CreditRule | null>(null);
  const [form,    setForm]    = useState<Omit<CreditRule, "id">>(BLANK);
  const [errors,  setErrors]  = useState<Record<string, string>>({});
  const [saving,  setSaving]  = useState(false);

  // Track the current FY until the admin picks a different one explicitly —
  // this only matters in the rare case the FY config resolves (from
  // localStorage, after mount) to a value other than the calendar-year default.
  useEffect(() => {
    if (!yearEdited) setCreditYear(fy.currentYear);
  }, [fy.currentYear, yearEdited]);

  async function creditAll() {
    setCrediting(true);
    setCreditResult(null);
    setCreditError(null);
    try {
      const res = await clientApi.post<{ data: { year: number; credited: number } }>(
        API.leave.balanceCredit,
        { year: creditYear }
      );
      setCreditResult(res.data.data);
    } catch (err: unknown) {
      setCreditError((err as { message?: string })?.message ?? "Failed to credit balances.");
    } finally {
      setCrediting(false);
    }
  }

  function openAdd() { setEditing(null); setForm(BLANK); setErrors({}); setModal("add"); }
  function openEdit(r: CreditRule) {
    setEditing(r);
    const { id: _id, ...rest } = r; void _id;
    setForm(rest); setErrors({}); setModal("edit");
  }
  function closeModal() { setModal(null); setEditing(null); }

  function validate(): boolean {
    const e: Record<string, string> = {};
    const leaveType = form.leave_type.trim();
    if (!leaveType) e.leave_type = "Leave type is required.";
    else if (!LEAVE_NAME_RE.test(leaveType)) e.leave_type = "Leave type can only contain letters, spaces, and hyphens — no numbers or special characters.";
    else if (rules.some(r => r.leave_type.trim().toLowerCase() === leaveType.toLowerCase() && r.id !== editing?.id)) {
      e.leave_type = `A credit rule for "${leaveType}" already exists.`;
    }
    if (form.accrual_days <= 0)                   e.accrual_days = "Must be greater than 0.";
    if (form.max_balance < 1)                     e.max_balance  = "Max balance must be at least 1.";
    if (form.encashable && form.encash_limit < 1) e.encash_limit = "Encash limit must be at least 1.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function save() {
    if (!validate()) return;
    setSaving(true);
    setTimeout(() => {
      if (modal === "add") setRules(prev => [...prev, { ...form, id: Date.now() }]);
      else if (editing) setRules(prev => prev.map(r => r.id === editing.id ? { ...form, id: editing.id } : r));
      setSaving(false); closeModal();
    }, 300);
  }

  function remove(id: number) {
    if (!window.confirm("Delete this credit rule?")) return;
    setRules(prev => prev.filter(r => r.id !== id));
  }

  function field(key: keyof typeof form, value: string | number | boolean) {
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });
    setForm(prev => ({ ...prev, [key]: value }));
  }

  return (
    <>
      {/* Credit action */}
      <div className="card mb-20" style={{ border: "1.5px solid rgba(30,78,140,0.25)", background: "rgba(30,78,140,0.03)" }}>
        <div className="card-header" style={{ borderBottom: "1px solid var(--outline-v)" }}>
          <div className="card-title"><i className="ti ti-coin" /> Credit Leave Balances</div>
        </div>
        <div style={{ padding: "20px 24px" }}>
          <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 16, lineHeight: 1.6 }}>
            Credit annual leave balances for all active employees based on the configured Leave Policy.
            Employees who already have a balance record for the selected year are skipped automatically.
          </p>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
            <div className="field-group" style={{ marginBottom: 0 }}>
              <label className="field-label">Financial Year</label>
              <input
                className="field-input"
                type="number" min={2020} max={2099}
                value={creditYear}
                onChange={e => { setYearEdited(true); setCreditResult(null); setCreditError(null); setCreditYear(Number(e.target.value)); }}
                style={{ width: 110 }}
              />
            </div>
            <button className="btn btn-filled" onClick={creditAll} disabled={crediting}>
              {crediting ? <><Spin />&nbsp;Crediting…</> : <><i className="ti ti-send" /> Credit All Employees</>}
            </button>
          </div>
          {creditResult && (
            <div style={{ marginTop: 14, padding: "12px 16px", background: "rgba(27,138,107,0.08)", border: "1px solid rgba(27,138,107,0.25)", borderRadius: 8, color: "var(--success)", fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
              <i className="ti ti-circle-check" style={{ fontSize: 16 }} />
              <span>
                {creditResult.credited === 0
                  ? `All employees already have balances for ${creditYear}. No new records created.`
                  : `Credited ${creditResult.credited} leave balance record${creditResult.credited !== 1 ? "s" : ""} for ${creditYear}.`}
              </span>
            </div>
          )}
          {creditError && (
            <div style={{ marginTop: 14, padding: "12px 16px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>{creditError}</div>
          )}
        </div>
      </div>

      {/* Accrual rules */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-refresh" /> Accrual Rules</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 11, color: "var(--outline)", background: "var(--outline-v)", padding: "2px 8px", borderRadius: 4 }}>Automation coming soon</span>
            <button className="btn btn-ghost" style={{ fontSize: 12, height: 30, padding: "0 12px" }} onClick={openAdd}>
              <i className="ti ti-plus" /> Add Rule
            </button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Leave Type</th>
                <th style={{ textAlign: "center" }}>Accrual Days</th>
                <th style={{ textAlign: "center" }}>Frequency</th>
                <th style={{ textAlign: "center" }}>Max Balance</th>
                <th style={{ textAlign: "center" }}>Encashable</th>
                <th style={{ textAlign: "center" }}>Min Service</th>
                <th style={{ textAlign: "center" }}>Status</th>
                <th style={{ textAlign: "center" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map(r => (
                <tr key={r.id}>
                  <td style={{ fontWeight: 600, fontSize: 13 }}>{r.leave_type}</td>
                  <td style={{ textAlign: "center" }}>
                    <span style={{ fontWeight: 700, fontSize: 15, color: "var(--primary)" }}>{r.accrual_days}</span>
                    <span style={{ fontSize: 11, color: "var(--on-variant)", marginLeft: 3 }}>days</span>
                  </td>
                  <td style={{ textAlign: "center" }}><span className="badge badge-info">{FREQ_LABELS[r.frequency]}</span></td>
                  <td style={{ textAlign: "center", fontWeight: 600 }}>{r.max_balance}d</td>
                  <td style={{ textAlign: "center" }}>
                    {r.encashable ? <span className="badge badge-success">Up to {r.encash_limit}d</span> : <span className="badge badge-neutral">No</span>}
                  </td>
                  <td style={{ textAlign: "center", fontSize: 13 }}>
                    {r.min_service_months > 0 ? `${r.min_service_months} months` : <span style={{ color: "var(--outline)" }}>—</span>}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <span className={`badge ${r.is_active ? "badge-success" : "badge-neutral"}`}>{r.is_active ? "Active" : "Inactive"}</span>
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
                      <button className="btn btn-ghost" style={{ width: 28, height: 28, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6 }} onClick={() => openEdit(r)}>
                        <i className="ti ti-edit" style={{ fontSize: 13 }} />
                      </button>
                      <button className="btn btn-ghost" style={{ width: 28, height: 28, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6, color: "var(--error)" }} onClick={() => remove(r.id)}>
                        <i className="ti ti-trash" style={{ fontSize: 13 }} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal */}
      {modal && (
        <div className="modal-overlay open">
          <div className="modal" style={{ maxWidth: 520 }}>
            <div className="modal-header">
              <div className="modal-title">
                <i className="ti ti-coin" style={{ marginRight: 8 }} />
                {modal === "add" ? "Add Credit Rule" : `Edit: ${editing?.leave_type}`}
              </div>
              <button className="modal-close" onClick={closeModal}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
                <div className="field-group mb-16" style={{ gridColumn: "1 / -1" }}>
                  <label className="field-label">Leave Type *</label>
                  <input className={`field-input${errors.leave_type ? " field-error" : ""}`} value={form.leave_type} onChange={e => field("leave_type", sanitizeLeaveName(e.target.value))} placeholder="e.g. Earned Leave" autoFocus />
                  {errors.leave_type && <p className="field-error-msg">{errors.leave_type}</p>}
                </div>
                <div className="field-group mb-16">
                  <label className="field-label">Accrual Days *</label>
                  <input className={`field-input${errors.accrual_days ? " field-error" : ""}`} type="number" step="0.5" min={0.5} value={form.accrual_days} onChange={e => field("accrual_days", Number(e.target.value))} />
                  {errors.accrual_days && <p className="field-error-msg">{errors.accrual_days}</p>}
                </div>
                <div className="field-group mb-16">
                  <label className="field-label">Frequency</label>
                  <select className="field-input" value={form.frequency} onChange={e => field("frequency", e.target.value)}>
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="annually">Annually</option>
                    <option value="on_joining">On Joining</option>
                  </select>
                </div>
                <div className="field-group mb-16">
                  <label className="field-label">Max Balance (days) *</label>
                  <input className={`field-input${errors.max_balance ? " field-error" : ""}`} type="number" min={1} value={form.max_balance} onChange={e => field("max_balance", Number(e.target.value))} />
                  {errors.max_balance && <p className="field-error-msg">{errors.max_balance}</p>}
                </div>
                <div className="field-group mb-16">
                  <label className="field-label">Min Service (months)</label>
                  <input className="field-input" type="number" min={0} value={form.min_service_months} onChange={e => field("min_service_months", Number(e.target.value))} />
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 14, flexWrap: "wrap" }}>
                <label className="module-check" style={{ flex: 1 }}>
                  <input type="checkbox" checked={form.encashable} onChange={e => field("encashable", e.target.checked)} />
                  <span>Allow Encashment</span>
                </label>
                {form.encashable && (
                  <div className="field-group" style={{ width: 160 }}>
                    <label className="field-label">Encash Limit (days) *</label>
                    <input className={`field-input${errors.encash_limit ? " field-error" : ""}`} type="number" min={1} value={form.encash_limit} onChange={e => field("encash_limit", Number(e.target.value))} />
                    {errors.encash_limit && <p className="field-error-msg">{errors.encash_limit}</p>}
                  </div>
                )}
                <label className="module-check">
                  <input type="checkbox" checked={form.is_active} onChange={e => field("is_active", e.target.checked)} />
                  <span>Active</span>
                </label>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={closeModal}>Cancel</button>
              <button className="btn btn-filled" onClick={save} disabled={saving}>
                {saving ? <><Spin />&nbsp;Saving…</> : modal === "add" ? "Add Rule" : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
