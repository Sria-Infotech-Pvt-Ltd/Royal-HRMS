"use client";

import type { CarryForwardType, CarryForwardMode, LeavePolicyCarryForwardSettings } from "@/types/leave";
import { ToggleRow } from "./LeavePoliciesTab";

type ExpiryMode = "never" | "after";

interface Props {
  cf:         LeavePolicyCarryForwardSettings;
  expiryMode: ExpiryMode;
  onExpiryModeChange: (mode: ExpiryMode) => void;
  setField: <K extends keyof LeavePolicyCarryForwardSettings>(key: K, value: LeavePolicyCarryForwardSettings[K]) => void;
  errors:    { max_carry_forward_days?: string; carry_forward_expiry_days?: string };
  saveError: string | null;
}

function RadioCard({ active, title, subtitle, onClick }: { active: boolean; title: string; subtitle: string; onClick: () => void }) {
  return (
    <label
      onClick={onClick}
      style={{
        flex: 1, display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer",
        padding: "12px 14px", borderRadius: 8,
        border: `1.5px solid ${active ? "var(--primary)" : "var(--outline-v)"}`,
        background: active ? "rgba(124,58,237,0.05)" : "transparent",
        transition: "border-color 0.15s, background 0.15s",
      }}
    >
      <input type="radio" checked={active} onChange={onClick} style={{ accentColor: "var(--primary)", marginTop: 2, flexShrink: 0 }} />
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{title}</div>
        <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2, lineHeight: 1.4 }}>{subtitle}</div>
      </div>
    </label>
  );
}

export default function CarryForwardSettingsSection({ cf, expiryMode, onExpiryModeChange, setField, errors, saveError }: Props) {
  return (
    <div className="card mb-20">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-repeat" /> Carry Forward Settings</div>
      </div>
      <div style={{ padding: "20px 24px" }}>
        {saveError && (
          <div style={{ marginBottom: 16, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>{saveError}</div>
        )}

        <div style={{ marginBottom: cf.can_carry_forward ? 20 : 0 }}>
          <ToggleRow label="Carry Forward Enabled" checked={cf.can_carry_forward} onChange={v => setField("can_carry_forward", v)} />
        </div>

        {cf.can_carry_forward && (
          <>
            <div className="field-group mb-16">
              <label className="field-label">Carry Forward Type</label>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <RadioCard
                  active={cf.carry_forward_type === "unlimited"}
                  title="Unlimited"
                  subtitle="Carry forward all remaining leave to the next leave year."
                  onClick={() => setField("carry_forward_type", "unlimited" as CarryForwardType)}
                />
                <RadioCard
                  active={cf.carry_forward_type === "limited"}
                  title="Limited"
                  subtitle="Carry forward leave up to the maximum days configured below."
                  onClick={() => setField("carry_forward_type", "limited" as CarryForwardType)}
                />
              </div>
            </div>

            {cf.carry_forward_type === "limited" && (
              <div className="field-group mb-16" style={{ maxWidth: 260 }}>
                <label className="field-label">Maximum Carry Forward Days</label>
                <input
                  className={`field-input${errors.max_carry_forward_days ? " field-error" : ""}`}
                  type="number" min={1} placeholder="e.g. 5"
                  value={cf.max_carry_forward_days || ""}
                  onChange={e => setField("max_carry_forward_days", Number(e.target.value))}
                />
                {errors.max_carry_forward_days && <p className="field-error-msg">{errors.max_carry_forward_days}</p>}
              </div>
            )}

            <div className="field-group mb-16">
              <label className="field-label">Carry Forward Mode</label>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <RadioCard
                  active={cf.carry_forward_mode === "automatic"}
                  title="Automatic"
                  subtitle="The system automatically carries forward eligible leave on 1st January each year."
                  onClick={() => setField("carry_forward_mode", "automatic" as CarryForwardMode)}
                />
                <RadioCard
                  active={cf.carry_forward_mode === "manual"}
                  title="Manual"
                  subtitle="HR / System Admin manually initiates carry forward from the Carry Forward tab."
                  onClick={() => setField("carry_forward_mode", "manual" as CarryForwardMode)}
                />
              </div>
            </div>

            <div className="field-group mb-4">
              <label className="field-label">Carry Forward Expiry</label>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <label style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer" }} onClick={() => { onExpiryModeChange("never"); setField("carry_forward_expiry_days", 0); }}>
                  <input type="radio" checked={expiryMode === "never"} onChange={() => { onExpiryModeChange("never"); setField("carry_forward_expiry_days", 0); }} style={{ accentColor: "var(--primary)", marginTop: 2, flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>Never Expire</div>
                    <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2 }}>Carried-forward leave remains valid until it is used.</div>
                  </div>
                </label>
                <label style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer" }} onClick={() => onExpiryModeChange("after")}>
                  <input type="radio" checked={expiryMode === "after"} onChange={() => onExpiryModeChange("after")} style={{ accentColor: "var(--primary)", marginTop: 2, flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>Expire After</span>
                      <input
                        className={`field-input${errors.carry_forward_expiry_days ? " field-error" : ""}`}
                        type="number" min={1} placeholder="e.g. 90"
                        style={{ width: 100 }}
                        disabled={expiryMode !== "after"}
                        value={expiryMode === "after" && cf.carry_forward_expiry_days > 0 ? cf.carry_forward_expiry_days : ""}
                        onClick={e => e.stopPropagation()}
                        onChange={e => setField("carry_forward_expiry_days", Number(e.target.value))}
                      />
                      <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>Days</span>
                    </div>
                    <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2 }}>Unused carried-forward leave expires after the given number of days.</div>
                  </div>
                </label>
              </div>
              {errors.carry_forward_expiry_days && <p className="field-error-msg">{errors.carry_forward_expiry_days}</p>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
