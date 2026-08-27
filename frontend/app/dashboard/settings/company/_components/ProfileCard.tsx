"use client";

import type { ReactNode } from "react";

interface Props {
  icon: string;
  title: string;
  subtitle: string;
  action?: ReactNode;
  children: ReactNode;
}

export default function ProfileCard({ icon, title, subtitle, action, children }: Props) {
  return (
    <div
      className="card mb-24"
      style={{ borderRadius: "var(--radius-lg)", overflow: "hidden" }}
    >
      <div style={{ padding: "18px 24px", borderBottom: "1px solid var(--outline-v)", display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, flexShrink: 0,
            background: "rgba(30,78,140,0.1)", color: "var(--primary)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <i className={`ti ${icon}`} style={{ fontSize: 16 }} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: "var(--on-bg)" }}>{title}</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>{subtitle}</div>
          </div>
        </div>
        {action}
      </div>
      <div style={{ padding: "20px 24px" }}>
        {children}
      </div>
    </div>
  );
}
