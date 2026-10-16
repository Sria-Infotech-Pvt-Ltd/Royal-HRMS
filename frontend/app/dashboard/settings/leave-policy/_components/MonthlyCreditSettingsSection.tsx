"use client";

// Leave Policy → Monthly Credit Settings for the selected leave type.
// A change takes effect from the 1st of next month (monthly_rules_from);
// earlier months are never recalculated.

import type { CreditSchedule, MonthlyCreditSettings } from "@/types/leave";
import { ToggleRow } from "./LeavePoliciesTab";

const SCHEDULES: { value: CreditSchedule; title: string; subtitle: string }[] = [
  { value: "annual",  title: "Annual",  subtitle: "Annual entitlement is credited for the year (current behaviour)." },
  { value: "monthly", title: "Monthly", subtitle: "Credits are recorded month by month through Monthly Leave Management." },
];

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default function MonthlyCreditSettingsSection({ value, onChange, rulesFrom }: {
  value: MonthlyCreditSettings; onChange: (next: MonthlyCreditSettings) => void; rulesFrom?: string | null;
}) {
  return (
    <div className="card mb-20">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar-repeat" /> Monthly Credit Settings</div>
      </div>
      <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--on-bg)", marginBottom: 8 }}>Credit Schedule</div>
          <div role="radiogroup" aria-label="Credit Schedule" style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {SCHEDULES.map(s => {
              const active = value.credit_schedule === s.value;
              return (
                <label key={s.value} style={{
                  flex: "1 1 220px", display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer",
                  padding: "12px 14px", borderRadius: 8,
                  border: `1.5px solid ${active ? "var(--primary)" : "var(--outline-v)"}`,
                  background: active ? "rgba(30,78,140,0.05)" : "transparent",
                }}>
                  <input type="radio" name="credit_schedule" checked={active} style={{ accentColor: "var(--primary)", marginTop: 2 }}
                    onChange={() => onChange({ ...value, credit_schedule: s.value })} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{s.title}</div>
                    <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2, lineHeight: 1.4 }}>{s.subtitle}</div>
                  </div>
                </label>
              );
            })}
          </div>
        </div>

        {value.credit_schedule === "monthly" && (
          <ToggleRow
            label="Monthly Carry Forward (unused monthly credit rolls into the next month)"
            checked={value.monthly_carry_forward}
            onChange={v => onChange({ ...value, monthly_carry_forward: v })}
          />
        )}

        <div style={{ fontSize: 12, color: "var(--on-variant)", lineHeight: 1.6 }}>
          <div>
            <strong>Monthly</strong> leave types get no annual credit (Credit Rules, new joiners, yearly reset);
            credits are entered or imported in Monthly Leave Management, and leave is checked against each
            month&apos;s own credit.
          </div>
          <div>
            With Monthly Carry Forward <strong>off</strong>, the unused part of a month&apos;s credit expires at month
            end. Opening balances, carried-forward days and manual adjustments never expire, and leave that was
            pending when the month closed is protected.
          </div>
          <div>
            Changes take effect from the 1st of next month; earlier months and existing balances are not
            recalculated.{rulesFrom ? <> Current rules apply from <strong>{formatDate(rulesFrom)}</strong>.</> : null}
          </div>
        </div>
      </div>
    </div>
  );
}
