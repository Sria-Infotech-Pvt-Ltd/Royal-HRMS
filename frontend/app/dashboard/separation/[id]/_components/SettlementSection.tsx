"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import { useApiErrors } from "@/hooks/useApiErrors";
import ConfirmModal from "@/components/ConfirmModal";
import FieldError from "@/components/shared/FieldError";
import { formatRupees } from "@/lib/formatMoney";
import type { SeparationRequest, SettlementItem } from "@/types/separation";
import { fmtDateTime } from "../../_workflow";

interface Props {
  r: SeparationRequest;
}

const INR = formatRupees;

// A minus sign glued straight onto the currency symbol ("₹-1,50,000", UAT-016)
// reads as a rendering bug, not a number. Parentheses are the standard
// accounting convention for a negative amount — same fix already applied to
// BasicPayStep's deduction lines (see its INR_DEDUCTION, QA report #49).
const INR_SIGNED = (n: string | number) => {
  const value = Number(n);
  return value < 0 ? `(${INR(Math.abs(value))})` : INR(value);
};

// Manual line items HR/Finance enters by hand — see SettlementItem's own
// comment for why these (unlike pro-rata salary/leave encashment/notice
// recovery) are never auto-computed.
const MANUAL_FIELDS: { key: keyof SettlementItem; label: string; addsToNet: boolean }[] = [
  { key: "gratuity_amount",          label: "Gratuity",              addsToNet: true },
  { key: "statutory_bonus_amount",   label: "Statutory Bonus",       addsToNet: true },
  { key: "reimbursements_amount",    label: "Pending Reimbursements", addsToNet: true },
  { key: "advances_recovery_amount", label: "Advances Recovery",     addsToNet: false },
  { key: "tds_amount",               label: "TDS",                   addsToNet: false },
  { key: "pf_recovery_amount",       label: "PF Recovery",           addsToNet: false },
  { key: "pt_recovery_amount",       label: "Professional Tax",      addsToNet: false },
];

export default function SettlementSection({ r }: Props) {
  const { showToast } = useToast();
  const { data: settlement, loading, refetch } = useFetch<SettlementItem>(API.separation.settlement(r.id));

  const [form, setForm] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [confirmFinalize, setConfirmFinalize] = useState(false);
  const [isRecovery, setIsRecovery] = useState(false);
  const { fieldErrors, formError, handleError, clearAll, clearField } = useApiErrors();

  function setFormField(key: string, value: string) {
    setForm(prev => ({ ...prev, [key]: value }));
    clearField(key);
  }

  function startEdit() {
    if (!settlement) return;
    clearAll();
    setIsRecovery(settlement.is_recovery);
    setForm({
      gratuity_amount: settlement.gratuity_amount,
      statutory_bonus_amount: settlement.statutory_bonus_amount,
      reimbursements_amount: settlement.reimbursements_amount,
      advances_recovery_amount: settlement.advances_recovery_amount,
      tds_amount: settlement.tds_amount,
      pf_recovery_amount: settlement.pf_recovery_amount,
      pt_recovery_amount: settlement.pt_recovery_amount,
      other_adjustment_amount: settlement.other_adjustment_amount,
      other_adjustment_note: settlement.other_adjustment_note,
    });
    setEditing(true);
  }

  async function save() {
    setSaving(true);
    clearAll();
    try {
      await clientApi.patch(API.separation.settlement(r.id), { ...form, is_recovery: isRecovery });
      showToast("Settlement updated.", "success");
      setEditing(false);
      refetch();
    } catch (err: unknown) {
      // Stay in edit mode: the person fixes the field the message points at and saves again.
      handleError(err, "Failed to update the settlement.");
    } finally {
      setSaving(false);
    }
  }

  async function finalize() {
    setConfirmFinalize(false);
    setFinalizing(true);
    clearAll();
    try {
      await clientApi.post(API.separation.settlementFinalize(r.id), {});
      showToast("Settlement finalized.", "success");
      refetch();
    } catch (err: unknown) {
      handleError(err, "Failed to finalize the settlement.");
    } finally {
      setFinalizing(false);
    }
  }

  if (loading) {
    return (
      <div className="card mb-16">
        <div className="card-header"><span className="card-title"><i className="ti ti-cash" /> Full &amp; Final Settlement</span></div>
        <div className="card-body"><p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}><i className="ti ti-loader-2 spin" /> Loading…</p></div>
      </div>
    );
  }
  if (!settlement) return null;

  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-cash" /> Full &amp; Final Settlement</span>
        <span className={`badge ${settlement.status === "finalized" ? "badge-success" : "badge-warn"}`}>
          {settlement.status_display}
        </span>
      </div>
      <div className="card-body">
        {formError && <div className="alert alert-error" style={{ marginBottom: 12 }}><i className="ti ti-alert-circle" /> {formError}</div>}
        <p style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 0, marginBottom: 16 }}>
          Pro-rated salary, leave encashment, and notice-period shortfall are computed automatically
          (CTC ÷ 30, Earned Leave balance) — a starting estimate to review, not a final figure.
          Gratuity, bonus, reimbursements, advances, and TDS are always entered by hand.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 8 }}>
          <Stat label="Pro-rata Salary" value={INR(settlement.pro_rata_salary)} />
          <Stat
            label="Leave Encashment"
            value={INR(settlement.leave_encashment_amount)}
            sub={`${settlement.leave_encashment_days} earned leave day(s)`}
          />
          <Stat
            label="Notice Period Recovery"
            value={`− ${INR(settlement.notice_period_recovery_amount)}`}
            sub={
              settlement.notice_period_shortfall_days > 0
                ? `${settlement.notice_period_served_days}/${settlement.notice_period_required_days} days served — ${settlement.notice_period_shortfall_days} day shortfall`
                : `Full ${settlement.notice_period_required_days}-day notice served`
            }
            warn={settlement.notice_period_shortfall_days > 0}
          />
        </div>

        {settlement.notice_period_shortfall_days > 0 && (
          <div className="alert alert-warning" role="status" style={{ marginBottom: 12 }}>
            <i className="ti ti-alert-triangle" />
            <div>
              <b>Notice period shortfall:</b> {settlement.notice_period_served_days} of {settlement.notice_period_required_days} days served
              ({settlement.notice_period_shortfall_days} short). A recovery of {INR(settlement.notice_period_recovery_amount)} has been calculated.
              Confirm with HR or finance whether this recovery applies before finalising.
            </div>
          </div>
        )}

        {!editing ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 16 }}>
              {MANUAL_FIELDS.map(f => (
                <Stat
                  key={f.key}
                  label={f.label}
                  value={`${f.addsToNet ? "+" : "−"} ${INR(settlement[f.key] as string)}`}
                />
              ))}
            </div>
            {Number(settlement.other_adjustment_amount) !== 0 && (
              <p style={{ fontSize: 13, marginBottom: 16 }}>
                Other Adjustment: {INR(settlement.other_adjustment_amount)}
                {settlement.other_adjustment_note && ` — ${settlement.other_adjustment_note}`}
              </p>
            )}

            <div style={{ borderTop: "1px solid var(--outline-v)", paddingTop: 12, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".05em", color: "var(--on-variant)" }}>
                  {settlement.is_recovery ? "Net Recoverable from Employee" : "Net Payable"}
                </div>
                <div style={{ fontSize: 22, fontWeight: 700, color: Number(settlement.net_payable_amount) < 0 ? "var(--error)" : undefined }}>
                  {INR(settlement.net_payable_amount)}
                </div>
                {settlement.is_recovery && (
                  <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>Recovery from the employee</div>
                )}
              </div>
              {settlement.status === "finalized" ? (
                <div style={{ fontSize: 12, color: "var(--on-variant)", textAlign: "right" }}>
                  Finalized by {settlement.finalized_by_name}
                  {settlement.finalized_at && <><br />{fmtDateTime(settlement.finalized_at)}</>}
                </div>
              ) : settlement.can_edit && (
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-ghost btn-sm" onClick={startEdit} suppressHydrationWarning>
                    <i className="ti ti-edit" /> Edit
                  </button>
                  <button className="btn btn-success btn-sm" onClick={() => setConfirmFinalize(true)} disabled={finalizing} suppressHydrationWarning>
                    {finalizing ? "Finalizing…" : <><i className="ti ti-check" /> Finalize</>}
                  </button>
                </div>
              )}
            </div>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
              {MANUAL_FIELDS.map(f => (
                <div className="field-group" key={f.key}>
                  <label className="field-label">{f.label}</label>
                  <input
                    className={`field-input${fieldErrors[f.key] ? " field-error" : ""}`} type="number" min="0"
                    value={form[f.key] ?? ""}
                    onChange={e => setFormField(f.key, e.target.value)}
                  />
                  <FieldError message={fieldErrors[f.key]} />
                </div>
              ))}
            </div>
            <div className="field-group">
              <label className="field-label">Other Adjustment (+/−)</label>
              <input
                className={`field-input${fieldErrors.other_adjustment_amount ? " field-error" : ""}`} type="number"
                value={form.other_adjustment_amount ?? ""}
                onChange={e => setFormField("other_adjustment_amount", e.target.value)}
              />
              <FieldError message={fieldErrors.other_adjustment_amount} />
            </div>
            <div className="field-group">
              <label className="field-label">Other Adjustment Note</label>
              <input
                className={`field-input${fieldErrors.other_adjustment_note ? " field-error" : ""}`} placeholder="What this adjustment is for"
                value={form.other_adjustment_note ?? ""}
                onChange={e => setFormField("other_adjustment_note", e.target.value)}
              />
              <FieldError message={fieldErrors.other_adjustment_note} />
            </div>
            <div className="field-group">
              <label className="module-check">
                <input type="checkbox" checked={isRecovery} onChange={e => { setIsRecovery(e.target.checked); clearField("is_recovery"); }} />
                <span>This is a recovery — the employee owes the company (net payable may be negative)</span>
              </label>
              <FieldError message={fieldErrors.is_recovery} />
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setEditing(false)} disabled={saving} suppressHydrationWarning>
                Cancel
              </button>
              <button className="btn btn-filled btn-sm" onClick={save} disabled={saving} suppressHydrationWarning>
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        )}
      </div>

      {confirmFinalize && (
        <ConfirmModal
          title="Finalize this settlement?"
          body={`This locks the full & final settlement at a net ${settlement.is_recovery ? "recoverable from the employee" : "payable"} of ${INR_SIGNED(settlement.net_payable_amount)}. Once finalized, no field on this settlement — gratuity, bonus, reimbursements, advances, TDS, or adjustments — can be edited again. This cannot be undone.`}
          confirmLabel="Finalize"
          danger
          saving={finalizing}
          onConfirm={finalize}
          onCancel={() => setConfirmFinalize(false)}
        />
      )}
    </div>
  );
}

function Stat({ label, value, sub, warn }: { label: string; value: string; sub?: string; warn?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".05em", color: "var(--on-variant)" }}>
        {label}
      </div>
      <div style={{ fontSize: 15, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: warn ? "var(--error)" : "var(--on-variant)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}
