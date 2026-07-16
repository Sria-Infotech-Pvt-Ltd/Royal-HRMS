"use client";

interface Props {
  checked:  boolean;
  onChange: (checked: boolean) => void;
  label?:   string;
  disabled?: boolean;
}

export default function ToggleSwitch({ checked, onChange, label, disabled }: Props) {
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 10, cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1 }}>
      <span
        onClick={() => { if (!disabled) onChange(!checked); }}
        style={{
          position: "relative", width: 38, height: 22, borderRadius: 11, flexShrink: 0,
          background: checked ? "var(--primary)" : "var(--outline-v)", transition: "background 0.15s",
        }}
      >
        <span
          style={{
            position: "absolute", top: 2, left: checked ? 18 : 2,
            width: 18, height: 18, borderRadius: "50%", background: "#fff",
            boxShadow: "0 1px 3px rgba(0,0,0,0.3)", transition: "left 0.15s",
          }}
        />
      </span>
      {label && <span style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{label}</span>}
    </label>
  );
}
