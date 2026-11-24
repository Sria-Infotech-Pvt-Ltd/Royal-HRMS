"use client";

// Shared look for the single-purpose Approvals tabs (Timesheets, Personnel actions, Face registration):
// a header with an icon, subtitle and stat chips, plus one empty state and one avatar.
import type { CSSProperties, ReactNode } from "react";
import { useT } from "@/hooks/useI18n";
import { initials } from "../_data";

export interface TabStat {
  label: string;
  value: number | string;
  icon: string;
  accent: string;
  /** Highlights the chip when this number means somebody has work to do. */
  isUrgent?: boolean;
}

interface HeaderProps {
  icon: string;
  title: string;
  subtitle: string;
  accent: string;
  stats?: TabStat[];
  /** Filters or switches shown at the right of the header. */
  actions?: ReactNode;
}

export function TabHeader({ icon, title, subtitle, accent, stats = [], actions }: HeaderProps) {
  const t = useT();
  return (
    <div className="tb-head" style={{ "--tb-accent": accent } as CSSProperties}>
      <div className="tb-head-main">
        <span className="tb-icon"><i className={`ti ${icon}`} /></span>
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </div>
      {actions && <div className="tb-actions">{actions}</div>}
      {stats.length > 0 && (
        <div className="tb-stats">
          {stats.map(stat => (
            <span key={stat.label} className={`tb-stat${stat.isUrgent ? " is-urgent" : ""}`} style={{ "--tb-stat": stat.accent } as CSSProperties}>
              <i className={`ti ${stat.icon}`} /> {t(stat.label)} <b>{stat.value}</b>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

interface EmptyProps {
  icon: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}

export function TabEmpty({ icon, title, hint, action }: EmptyProps) {
  return (
    <div className="tb-empty">
      <span className="tb-empty-icon"><i className={`ti ${icon}`} /></span>
      <div className="tb-empty-title">{title}</div>
      {hint && <div className="tb-empty-hint">{hint}</div>}
      {action && <div style={{ marginTop: 12 }}>{action}</div>}
    </div>
  );
}

export function PersonAvatar({ name }: { name: string }) {
  return <span className="tb-avatar" aria-hidden="true">{initials(name)}</span>;
}
