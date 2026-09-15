"use client";

import Modal from "@/components/Modal";
import { PROVIDER_ORDER, PROVIDER_META, type Provider } from "../_data";

interface Props {
  onSelect: (provider: Exclude<Provider, "">) => void;
  onClose:  () => void;
}

export default function ProviderSelectModal({ onSelect, onClose }: Props) {
  return (
    <Modal
      title="Add SMTP Configuration"
      onClose={onClose}
      size="lg"
      footer={
        <button className="btn btn-ghost" onClick={onClose} suppressHydrationWarning>Cancel</button>
      }
    >
      <p style={{ fontSize: 13, color: "var(--on-variant)", margin: "0 0 18px" }}>
        Choose a mail provider — the fields you need will be filled in for you where possible.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3" style={{ gap: 14 }}>
        {PROVIDER_ORDER.map(value => {
          const meta = PROVIDER_META[value];
          return (
            <button
              key={value}
              type="button"
              onClick={() => onSelect(value)}
              style={{
                textAlign: "left", padding: "16px", borderRadius: "var(--radius-lg)",
                border: "1.5px solid var(--outline-v)", background: "#fff",
                cursor: "pointer", transition: "border-color 0.15s, box-shadow 0.15s",
                display: "flex", flexDirection: "column", gap: 10,
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--primary)"; e.currentTarget.style.boxShadow = "0 2px 10px rgba(30,78,140,0.08)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--outline-v)"; e.currentTarget.style.boxShadow = "none"; }}
              suppressHydrationWarning
            >
              <div style={{
                width: 38, height: 38, borderRadius: 10, flexShrink: 0,
                background: meta.iconBg, color: meta.iconColor,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <i className={`ti ${meta.icon}`} style={{ fontSize: 18 }} />
              </div>
              <div>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--on-bg)" }}>{meta.label}</div>
                <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 4, lineHeight: 1.45 }}>
                  {meta.description}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </Modal>
  );
}
