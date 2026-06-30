"use client";

import { useState } from "react";
import { EMP_DATA, fmt } from "./payrollData";

interface Props { onNext: () => void; onBack: () => void; }

interface ReimbRow { id: string; name: string; avatar: string; dept: string; travel: number; fuel: number; medical: number; internet: number; food: number; }
interface BonusRow { id: string; name: string; avatar: string; dept: string; bonus: number; incentive: number; festival: number; perf_bonus: number; }

const INIT_REIMB: ReimbRow[] = EMP_DATA.map(e => ({ id: e.id, name: e.name, avatar: e.avatar, dept: e.dept, travel: e.travel, fuel: e.fuel, medical: e.medical, internet: e.internet, food: e.food }));
const INIT_BONUS: BonusRow[] = EMP_DATA.map(e => ({ id: e.id, name: e.name, avatar: e.avatar, dept: e.dept, bonus: e.bonus, incentive: e.incentive, festival: e.festival, perf_bonus: e.perf_bonus }));

const BONUS_COLORS = ["#1e4e8c","#1b8a6b","#b5651d","#ad95cf","#0e7c86"];

function totalReimb(r: ReimbRow) { return r.travel + r.fuel + r.medical + r.internet + r.food; }
function totalBonus(b: BonusRow) { return b.bonus + b.incentive + b.festival + b.perf_bonus; }

function Av({ text, color }: { text: string; color: string }) {
  return (
    <div style={{ width: 28, height: 28, borderRadius: "50%", background: color, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>
      {text}
    </div>
  );
}

export default function ReimbBonusesStep({ onNext, onBack }: Props) {
  const [reimbs, setReimbs] = useState<ReimbRow[]>(INIT_REIMB);
  const [bonuses, setBonuses] = useState<BonusRow[]>(INIT_BONUS);
  const [editBonus, setEditBonus] = useState<number | null>(null);
  const [bonusDraft, setBonusDraft] = useState<Partial<BonusRow>>({});
  const [showAddReimb, setShowAddReimb] = useState(false);
  const [newReimb, setNewReimb] = useState({ name: "", travel: 0, fuel: 0, medical: 0, internet: 0, food: 0 });

  const grandReimb = reimbs.reduce((s, r) => s + totalReimb(r), 0);
  const grandBonus = bonuses.reduce((s, b) => s + totalBonus(b), 0);

  function saveBonus() {
    if (editBonus === null) return;
    setBonuses(prev => prev.map((b, i) => i === editBonus ? { ...b, ...bonusDraft } as BonusRow : b));
    setEditBonus(null);
  }

  function addReimb() {
    const key = `NEW${reimbs.length}`;
    setReimbs(r => [...r, { id: key, avatar: newReimb.name.slice(0, 2).toUpperCase() || "??", dept: "—", ...newReimb }]);
    setNewReimb({ name: "", travel: 0, fuel: 0, medical: 0, internet: 0, food: 0 });
    setShowAddReimb(false);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* ── Reimbursements ── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-receipt" /> Reimbursements</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Total: <strong style={{ color: "var(--info)" }}>{fmt(grandReimb)}</strong></span>
            <button className="btn btn-outline btn-sm" onClick={() => setShowAddReimb(true)}><i className="ti ti-plus" /> Add</button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th style={{ textAlign: "right" }}>Travel</th>
                <th style={{ textAlign: "right" }}>Fuel</th>
                <th style={{ textAlign: "right" }}>Medical</th>
                <th style={{ textAlign: "right" }}>Internet</th>
                <th style={{ textAlign: "right" }}>Food</th>
                <th style={{ textAlign: "right", color: "var(--info)" }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {reimbs.map((r, i) => (
                <tr key={r.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <Av text={r.avatar} color="var(--info)" />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{r.name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.dept}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ textAlign: "right" }}>{r.travel   > 0 ? fmt(r.travel)   : "—"}</td>
                  <td style={{ textAlign: "right" }}>{r.fuel     > 0 ? fmt(r.fuel)     : "—"}</td>
                  <td style={{ textAlign: "right" }}>{r.medical  > 0 ? fmt(r.medical)  : "—"}</td>
                  <td style={{ textAlign: "right" }}>{r.internet > 0 ? fmt(r.internet) : "—"}</td>
                  <td style={{ textAlign: "right" }}>{r.food     > 0 ? fmt(r.food)     : "—"}</td>
                  <td style={{ textAlign: "right", fontWeight: 700, color: "var(--info)" }}>{fmt(totalReimb(r))}</td>
                </tr>
              ))}
              <tr style={{ background: "var(--bg-low)" }}>
                <td style={{ fontWeight: 700 }}>Total</td>
                {(["travel","fuel","medical","internet","food"] as (keyof ReimbRow)[]).map(k => (
                  <td key={k as string} style={{ textAlign: "right", fontWeight: 600 }}>{fmt(reimbs.reduce((s, r) => s + (r[k] as number), 0))}</td>
                ))}
                <td style={{ textAlign: "right", fontWeight: 700, color: "var(--info)" }}>{fmt(grandReimb)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Bonuses & Incentives ── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-gift" /> Bonuses & Incentives</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Total: <strong style={{ color: "var(--warn)" }}>{fmt(grandBonus)}</strong></span>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th style={{ textAlign: "right" }}>Bonus</th>
                <th style={{ textAlign: "right" }}>Incentive</th>
                <th style={{ textAlign: "right" }}>Festival Bonus</th>
                <th style={{ textAlign: "right" }}>Performance Bonus</th>
                <th style={{ textAlign: "right", color: "var(--warn)" }}>Total</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {bonuses.map((b, idx) => (
                <tr key={b.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <Av text={b.avatar} color={BONUS_COLORS[idx % BONUS_COLORS.length]} />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{b.name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{b.dept}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ textAlign: "right" }}>{b.bonus      > 0 ? fmt(b.bonus)      : "—"}</td>
                  <td style={{ textAlign: "right" }}>{b.incentive  > 0 ? fmt(b.incentive)  : "—"}</td>
                  <td style={{ textAlign: "right" }}>{b.festival   > 0 ? fmt(b.festival)   : "—"}</td>
                  <td style={{ textAlign: "right" }}>{b.perf_bonus > 0 ? fmt(b.perf_bonus) : "—"}</td>
                  <td style={{ textAlign: "right", fontWeight: 700, color: totalBonus(b) > 0 ? "var(--warn)" : "var(--outline)" }}>
                    {totalBonus(b) > 0 ? fmt(totalBonus(b)) : "—"}
                  </td>
                  <td>
                    <button className="btn btn-ghost btn-sm" onClick={() => { setEditBonus(idx); setBonusDraft({ ...b }); }}>
                      <i className="ti ti-edit" />
                    </button>
                  </td>
                </tr>
              ))}
              <tr style={{ background: "var(--bg-low)" }}>
                <td style={{ fontWeight: 700 }}>Total</td>
                {(["bonus","incentive","festival","perf_bonus"] as (keyof BonusRow)[]).map(k => (
                  <td key={k as string} style={{ textAlign: "right", fontWeight: 600 }}>{fmt(bonuses.reduce((s, b) => s + (b[k] as number), 0))}</td>
                ))}
                <td style={{ textAlign: "right", fontWeight: 700, color: "var(--warn)" }}>{fmt(grandBonus)}</td>
                <td />
              </tr>
            </tbody>
          </table>
        </div>
        <div style={{ padding: "14px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
          <button className="btn btn-filled" onClick={onNext}>Continue <i className="ti ti-arrow-right" /></button>
        </div>
      </div>

      {/* Add Reimbursement modal */}
      {showAddReimb && (
        <div className="modal-overlay open" onClick={() => setShowAddReimb(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">Add Reimbursement</div>
              <button className="modal-close" onClick={() => setShowAddReimb(false)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              <div className="field-group" style={{ marginBottom: 14 }}>
                <label className="field-label">Employee Name</label>
                <input className="field-input" value={newReimb.name} onChange={e => setNewReimb(n => ({ ...n, name: e.target.value }))} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {(["travel","fuel","medical","internet","food"] as const).map(k => (
                  <div className="field-group" key={k}>
                    <label className="field-label">{k.charAt(0).toUpperCase() + k.slice(1)} (₹)</label>
                    <input type="number" className="field-input" value={newReimb[k]} onChange={e => setNewReimb(n => ({ ...n, [k]: Number(e.target.value) }))} />
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowAddReimb(false)}>Cancel</button>
              <button className="btn btn-filled" onClick={addReimb}>Add Row</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Bonus modal */}
      {editBonus !== null && (
        <div className="modal-overlay open" onClick={() => setEditBonus(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">Edit Bonuses — {bonuses[editBonus].name}</div>
              <button className="modal-close" onClick={() => setEditBonus(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {(["bonus","incentive","festival","perf_bonus"] as (keyof BonusRow)[]).map(k => (
                  <div className="field-group" key={k as string}>
                    <label className="field-label">{(k as string).replace("_"," ").replace(/\b\w/g, c => c.toUpperCase())} (₹)</label>
                    <input type="number" className="field-input" value={(bonusDraft[k] as number) ?? 0} onChange={ev => setBonusDraft(d => ({ ...d, [k]: Number(ev.target.value) }))} />
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setEditBonus(null)}>Cancel</button>
              <button className="btn btn-filled" onClick={saveBonus}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
