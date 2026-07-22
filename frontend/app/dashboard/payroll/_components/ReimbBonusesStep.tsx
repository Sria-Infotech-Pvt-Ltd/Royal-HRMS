"use client";

import { useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type {
  EmployeeExpenseSummary,
  EmployeePayslip,
  EmployeeReferralSummary,
} from "@/types/payroll";
import ReimbEditModal from "./ReimbEditModal";
import BonusEditModal from "./BonusEditModal";

interface Props {
  cycleId: string;
  enableReimbursements: boolean;
  enableBonuses: boolean;
  onNext: () => void;
  onBack: () => void;
}

interface PagedResponse<T> { results: T[]; count: number; }

const fmt = (n: number | string) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

export default function ReimbBonusesStep({
  cycleId, enableReimbursements, enableBonuses, onNext, onBack,
}: Props) {
  const { data: payslipPage, loading, refetch } =
    useFetch<PagedResponse<EmployeePayslip>>(API.payroll.cyclePayslips(cycleId));

  const { data: expenseSummaryRaw } =
    useFetch<EmployeeExpenseSummary[]>(enableReimbursements ? API.payroll.expenseSummary(cycleId) : null);

  const { data: referralSummaryRaw } =
    useFetch<EmployeeReferralSummary[]>(enableBonuses ? API.payroll.referralBonusSummary(cycleId) : null);

  const [reimbTarget, setReimbTarget] = useState<EmployeePayslip | null>(null);
  const [bonusTarget,  setBonusTarget]  = useState<EmployeePayslip | null>(null);

  const payslips = payslipPage?.results ?? [];

  // Index summaries by payslip_id for O(1) modal lookup
  const expenseMap = useMemo(() => {
    const map: Record<string, EmployeeExpenseSummary> = {};
    (expenseSummaryRaw ?? []).forEach(e => { map[e.payslip_id] = e; });
    return map;
  }, [expenseSummaryRaw]);

  const referralMap = useMemo(() => {
    const map: Record<string, EmployeeReferralSummary> = {};
    (referralSummaryRaw ?? []).forEach(r => { map[r.payslip_id] = r; });
    return map;
  }, [referralSummaryRaw]);

  const totalReimb = payslips.reduce((s, p) => s + Number(p.reimbursements), 0);
  const totalBonus = payslips.reduce((s, p) => s + Number(p.bonus), 0);

  function afterSave() { setReimbTarget(null); setBonusTarget(null); refetch(); }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {enableReimbursements && (
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title"><i className="ti ti-receipt" /> Reimbursements</div>
              <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>
                Approved expenses are auto-fetched. Click Edit to choose which to include.
              </div>
            </div>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Total: <strong style={{ color: "var(--info)" }}>{fmt(totalReimb)}</strong>
            </span>
          </div>
          {loading ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 20 }} />
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th style={{ textAlign: "right" }}>Pending Expenses</th>
                    <th style={{ textAlign: "right" }}>Included in Payroll</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {payslips.map(p => {
                    const summary = expenseMap[p.id];
                    const pendingCount = summary?.expenses.length ?? 0;
                    const includedCount = summary?.expenses.filter(e => e.already_included).length ?? 0;
                    return (
                      <tr key={p.id}>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--info)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700 }}>
                              {p.employee_name.charAt(0)}
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, fontSize: 13 }}>{p.employee_name}</div>
                              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.department}</div>
                            </div>
                          </div>
                        </td>
                        <td style={{ textAlign: "right", fontSize: 12, color: "var(--on-variant)" }}>
                          {pendingCount > 0 ? `${pendingCount} claim${pendingCount > 1 ? "s" : ""}` : "—"}
                        </td>
                        <td style={{ textAlign: "right", fontWeight: 600, color: Number(p.reimbursements) > 0 ? "var(--info)" : "var(--outline)" }}>
                          {Number(p.reimbursements) > 0 ? `${fmt(p.reimbursements)} (${includedCount})` : "—"}
                        </td>
                        <td>
                          <button className="btn btn-ghost btn-sm" onClick={() => setReimbTarget(p)}>
                            <i className="ti ti-edit" /> Edit
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  <tr style={{ background: "var(--bg-low)" }}>
                    <td style={{ fontWeight: 700 }} colSpan={2}>Total</td>
                    <td style={{ textAlign: "right", fontWeight: 700, color: "var(--info)" }}>{fmt(totalReimb)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {enableBonuses && (
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title"><i className="ti ti-gift" /> Bonuses</div>
              <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>
                Add Annual, Performance, Referral, or ad-hoc bonuses per employee.
              </div>
            </div>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Total: <strong style={{ color: "var(--warn)" }}>{fmt(totalBonus)}</strong>
            </span>
          </div>
          {loading ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 20 }} />
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th style={{ textAlign: "right" }}>Pending Referrals</th>
                    <th style={{ textAlign: "right" }}>Bonus Amount</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {payslips.map(p => {
                    const referrals = referralMap[p.id];
                    const referralCount = referrals?.referral_bonuses.length ?? 0;
                    return (
                      <tr key={p.id}>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--warn)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700 }}>
                              {p.employee_name.charAt(0)}
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, fontSize: 13 }}>{p.employee_name}</div>
                              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.department}</div>
                            </div>
                          </div>
                        </td>
                        <td style={{ textAlign: "right", fontSize: 12, color: referralCount > 0 ? "var(--warn)" : "var(--on-variant)" }}>
                          {referralCount > 0 ? `${referralCount} pending` : "—"}
                        </td>
                        <td style={{ textAlign: "right", fontWeight: 600, color: Number(p.bonus) > 0 ? "var(--warn)" : "var(--outline)" }}>
                          {Number(p.bonus) > 0 ? fmt(p.bonus) : "—"}
                          {p.bonus_breakdown?.length > 0 && (
                            <span style={{ marginLeft: 6, fontSize: 10, color: "var(--on-variant)", fontWeight: 400 }}>
                              ({p.bonus_breakdown.length} {p.bonus_breakdown.length === 1 ? "entry" : "entries"})
                            </span>
                          )}
                        </td>
                        <td>
                          <button className="btn btn-ghost btn-sm" onClick={() => setBonusTarget(p)}>
                            <i className="ti ti-edit" /> Edit
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  <tr style={{ background: "var(--bg-low)" }}>
                    <td style={{ fontWeight: 700 }} colSpan={2}>Total</td>
                    <td style={{ textAlign: "right", fontWeight: 700, color: "var(--warn)" }}>{fmt(totalBonus)}</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
        <button className="btn btn-filled" onClick={onNext}>Continue <i className="ti ti-arrow-right" /></button>
      </div>

      {reimbTarget && (
        <ReimbEditModal
          payslip={reimbTarget}
          summary={expenseMap[reimbTarget.id] ?? null}
          onSaved={afterSave}
          onClose={() => setReimbTarget(null)}
        />
      )}

      {bonusTarget && (
        <BonusEditModal
          payslip={bonusTarget}
          referralSummary={referralMap[bonusTarget.id] ?? null}
          onSaved={afterSave}
          onClose={() => setBonusTarget(null)}
        />
      )}
    </div>
  );
}
