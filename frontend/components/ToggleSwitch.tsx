"use client";

import type { ReactNode } from "react";

interface Props {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: ReactNode;
  disabled?: boolean;
}

export default function ToggleSwitch({ checked, onChange, label, disabled = false }: Props) {
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: "10px", cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1 }}>
      <span
        onClick={() => !disabled && onChange(!checked)}
        style={{
          position: "relative", width: "38px", height: "22px", borderRadius: "11px", flexShrink: 0,
          background: checked ? "var(--primary)" : "var(--outline-v)", transition: "background 0.15s",
        }}
      >
        <span
          style={{
            position: "absolute", top: "2px", left: checked ? "18px" : "2px",
            width: "18px", height: "18px", borderRadius: "50%", background: "var(--surface)",
            boxShadow: "0 1px 3px rgba(0,0,0,0.3)", transition: "left 0.15s",
          }}
        />
      </span>
      {label && <span style={{ fontSize: "13px", fontWeight: 500, color: "var(--on-bg)" }}>{label}</span>}
    </label>
  );
}
