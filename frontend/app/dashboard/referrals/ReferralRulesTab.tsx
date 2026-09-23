"use client";

import type { ReferralRule } from "./_data";

export default function ReferralRulesTab({ rules, loading }: { rules: ReferralRule[]; loading: boolean }) {
  return (
    <div style={{ padding: "28px 32px" }}>
      {loading ? (
        <div className="text-center py-10"><i className="ti ti-loader-2 spin text-3xl" /></div>
      ) : rules.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-file-text" />
          <h3>No rules configured</h3>
          <p>An admin can add referral rules from{" "}
            <strong>Settings → Referral Rules</strong>.
          </p>
        </div>
      ) : (
        <>
          <div className="alert alert-info" style={{ marginBottom: 24 }}>
            <i className="ti ti-info-circle" />
            <div>These rules govern the Employee Referral Programme. Please read them carefully before submitting a referral.</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))", gap: 20, marginBottom: 28 }}>
            {rules.map((rule, idx) => (
              <div key={rule.id} style={{ border: "1px solid var(--outline-v)", borderRadius: 14, padding: "20px 22px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
                  <div style={{ width: 38, height: 38, borderRadius: 10, background: "rgba(124,58,237,0.09)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <i className={`ti ${rule.icon}`} style={{ fontSize: 18, color: "var(--primary)" }} />
                  </div>
                  <div>
                    <span style={{ fontSize: 10, fontWeight: 700, color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                      Rule {idx + 1}
                    </span>
                    <p style={{ fontWeight: 700, fontSize: 14, color: "var(--on-bg)", margin: 0 }}>{rule.title}</p>
                  </div>
                </div>
                <p style={{ fontSize: 13, color: "var(--on-variant)", lineHeight: 1.65, margin: 0 }}>{rule.body}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
