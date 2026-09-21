"use client";

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { getLeaveYear } from "@/lib/fiscalYear";

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function CreditTab() {
  const [creditYear,  setCreditYear]  = useState<number>(getLeaveYear());
  const [crediting,    setCrediting]    = useState(false);
  const [creditResult, setCreditResult] = useState<{ credited: number } | null>(null);
  const [creditError,  setCreditError]  = useState<string | null>(null);

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

  return (
    <div className="card mb-20" style={{ border: "1.5px solid rgba(124,58,237,0.25)", background: "rgba(124,58,237,0.03)" }}>
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
            <label className="field-label">Year</label>
            <input
              className="field-input"
              type="number" min={2020} max={2099}
              value={creditYear}
              onChange={e => { setCreditResult(null); setCreditError(null); setCreditYear(Number(e.target.value)); }}
              style={{ width: 110 }}
            />
          </div>
          <button className="btn btn-filled" onClick={creditAll} disabled={crediting}>
            {crediting ? <><Spin />&nbsp;Crediting…</> : <><i className="ti ti-send" /> Credit All Employees</>}
          </button>
        </div>
        {creditResult && (
          <div style={{ marginTop: 14, padding: "12px 16px", background: "rgba(23,144,90,0.08)", border: "1px solid rgba(23,144,90,0.25)", borderRadius: 8, color: "var(--success)", fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
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
  );
}
