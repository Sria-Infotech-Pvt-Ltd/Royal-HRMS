"use client";

import type { ReactNode } from "react";

interface Props {
  icon: string;
  title: string;
  subtitle: string;
  action?: ReactNode;
  collapsed: boolean;
  onToggleCollapse: () => void;
  children: ReactNode;
}

export default function ProfileCard({ icon, title, subtitle, action, collapsed, onToggleCollapse, children }: Props) {
  return (
    <div
      className="card mb-24"
      style={{ borderRadius: "var(--radius-lg)", overflow: "hidden" }}
    >
      <div
        onClick={onToggleCollapse}
        style={{
          padding: "18px 24px", borderBottom: collapsed ? "none" : "1px solid var(--outline-v)",
          display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12,
          cursor: "pointer",
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, flexShrink: 0,
            background: "rgba(124,58,237,0.1)", color: "var(--primary)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <i className={`ti ${icon}`} style={{ fontSize: 16 }} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: "var(--on-bg)" }}>{title}</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>{subtitle}</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          {action && <span onClick={e => e.stopPropagation()}>{action}</span>}
          <i
            className="ti ti-chevron-down"
            style={{
              fontSize: 16, color: "var(--on-variant)", flexShrink: 0,
              transition: "transform 0.15s", transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)",
            }}
          />
        </div>
      </div>
      {!collapsed && (
        <div style={{ padding: "20px 24px" }}>
          {children}
        </div>
      )}
    </div>
  );
}
