"use client";

// The Basic pay dialog's three wage tables (Earnings / Employer contributions / Statutory deductions) and the
// totals under them — presentational; the amounts come from lib/payBreakup.ts.

import type { PayBreakup, PayLine, OverrideKey } from "@/lib/payBreakup";

const inr = (value: number) => `₹${Math.round(value).toLocaleString("en-IN")}`;

function Group({ title, badge, badgeClass, lines, editable, onChange }: {
  title: string;
  badge: string;
  badgeClass: "hr" | "adm";
  lines: PayLine[];
  editable: boolean;
  onChange: (key: OverrideKey, value: string) => void;
}) {
  return (
    <>
      <div className="sechead" style={{ marginTop: 10 }}>{title} <span className={`own ${badgeClass}`}>{badge}</span></div>
      <div className="wt-h"><div>CODE</div><div>DESCRIPTION</div><div>AMOUNT (₹)</div><div>BASIS</div><div /></div>
      {lines.map(line => (
        <div className="wt-r" key={line.code}>
          <div className="wt-code">{line.code}</div>
          <div><div className="wt-name">{line.name}</div></div>
          <div>
            <input
              className="finput pw"
              type="number"
              min={0}
              value={line.amount}
              disabled={!line.editable || !editable}
              onChange={event => { if (line.key) onChange(line.key, event.target.value); }}
              aria-label={`${line.name} amount`}
            />
          </div>
          <div className="wt-inval">{line.note}</div>
          <div>{line.editable ? <span className="own hr">HR</span> : <span className="tag">AUTO</span>}</div>
        </div>
      ))}
    </>
  );
}

export default function PayBreakupTables({ breakup, editable, variance, hasRecord, onChange }: {
  breakup: PayBreakup;
  editable: boolean;
  /** Annual cost to company minus the CTC on record. */
  variance: number;
  hasRecord: boolean;
  onChange: (key: OverrideKey, value: string) => void;
}) {
  return (
    <>
      <Group title="EARNINGS" badge="HR" badgeClass="hr" lines={breakup.earnings} editable={editable} onChange={onChange} />
      <Group title="EMPLOYER CONTRIBUTIONS" badge="STATUTORY" badgeClass="adm" lines={breakup.employer} editable={editable} onChange={onChange} />
      <Group title="STATUTORY DEDUCTIONS" badge="STATUTORY" badgeClass="adm" lines={breakup.deductions} editable={editable} onChange={onChange} />
      <div className="divider" style={{ margin: "10px 0" }} />
      <div className="paytot"><span>Monthly gross — paid to the employee</span><b>{inr(breakup.gross)}</b></div>
      <div className="paytot"><span>Employer contributions — on top of gross</span><b>{inr(breakup.employerTotal)}</b></div>
      <div className="paytot"><span>Monthly cost to company</span><b>{inr(breakup.monthlyCtc)}</b></div>
      <div className="paytot"><span>Annual cost to company</span><b>{inr(breakup.monthlyCtc * 12)}</b></div>
      <div className="paytot"><span>Statutory deductions</span><b>−{inr(breakup.deductionTotal)}</b></div>
      <div className="paytot"><span>Net take-home before income tax</span><b>{inr(breakup.net)}</b></div>
      {hasRecord && (
        <div className={`paytot${variance !== 0 ? " warn" : ""}`}>
          <span>Variance vs annual CTC on record</span>
          <b>{variance === 0 ? "Matches" : `${variance > 0 ? "+" : "−"}${inr(Math.abs(variance))}`}</b>
        </div>
      )}
    </>
  );
}
