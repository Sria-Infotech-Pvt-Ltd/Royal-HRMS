"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import type { SeparationRequest, SettlementItem } from "@/types/separation";
import { fmtDateTime } from "../../_workflow";

interface Props {
  r: SeparationRequest;
}

const INR = (n: string | number) =>
  `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

// Manual line items HR/Finance enters by hand — see SettlementItem's own
// comment for why these (unlike pro-rata salary/leave encashment/notice
// recovery) are never auto-computed.
const MANUAL_FIELDS: { key: keyof SettlementItem; label: string; addsToNet: boolean }[] = [
  { key: "gratuity_amount",          label: "Gratuity",              addsToNet: true },
  { key: "statutory_bonus_amount",   label: "Statutory Bonus",       addsToNet: true },
  { key: "reimbursements_amount",    label: "Pending Reimbursements", addsToNet: true },
  { key: "advances_recovery_amount", label: "Advances Recovery",     addsToNet: false },
  { key: "tds_amount",               label: "TDS",                   addsToNet: false },
];

export default function SettlementSection({ r }: Props) {
  const { showToast } = useToast();
  const { data: settlement, loading, refetch } = useFetch<SettlementItem>(API.separation.settlement(r.id));

  const [form, setForm] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [finalizing, setFinalizing] = useState(false);

  function extractError(err: unknown, fallback: string): string {
    return (err as { response?: { data?: { message?: string } }; message?: string })
      ?.response?.data?.message ?? (err as { message?: string })?.message ?? fallback;
  }

  function startEdit() {
    if (!settlement) return;
    setForm({
      gratuity_amount: settlement.gratuity_amount,
      statutory_bonus_amount: settlement.statutory_bonus_amount,
      reimbursements_amount: settlement.reimbursements_amount,
      advances_recovery_amount: settlement.advances_recovery_amount,
      tds_amount: settlement.tds_amount,
      other_adjustment_amount: settlement.other_adjustment_amount,
      other_adjustment_note: settlement.other_adjustment_note,
    });
    setEditing(true);
  }

  async function save() {
    setSaving(true);
    try {
      await clientApi.patch(API.separation.settlement(r.id), form);
      showToast("Settlement updated.", "success");
      setEditing(false);
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to update the settlement."), "error");
    } finally {
      setSaving(false);
    }
  }

  async function finalize() {
    setFinalizing(true);
    try {
      await clientApi.post(API.separation.settlementFinalize(r.id), {});
      showToast("Settlement finalized.", "success");
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to finalize the settlement."), "error");
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
                  Net Payable
                </div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{INR(settlement.net_payable_amount)}</div>
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
                  <button className="btn btn-success btn-sm" onClick={finalize} disabled={finalizing} suppressHydrationWarning>
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
                    className="field-input" type="number" min="0"
                    value={form[f.key] ?? ""}
                    onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                  />
                </div>
              ))}
            </div>
            <div className="field-group">
              <label className="field-label">Other Adjustment (+/−)</label>
              <input
                className="field-input" type="number"
                value={form.other_adjustment_amount ?? ""}
                onChange={e => setForm(prev => ({ ...prev, other_adjustment_amount: e.target.value }))}
              />
            </div>
            <div className="field-group">
              <label className="field-label">Other Adjustment Note</label>
              <input
                className="field-input" placeholder="What this adjustment is for"
                value={form.other_adjustment_note ?? ""}
                onChange={e => setForm(prev => ({ ...prev, other_adjustment_note: e.target.value }))}
              />
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
