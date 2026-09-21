"use client";

// The "Quick actions" right-hand card — bold heading, gray subtitle, a 2x2
// grid of QuickActionTile entries, then (optionally) the weekly bar chart
// beneath it, matching the reference layout used across every module page.

import { QuickActionTile, WeeklyBarChart } from "./ModuleOverviewKit";

export interface QuickActionItem {
  title: string;
  sub: string;
  onClick: () => void;
}

interface Props {
  title?: string;
  subtitle?: string;
  items: QuickActionItem[];
  chartData?: { label: string; count: number }[];
}

export default function QuickActionsGrid({
  title = "Quick actions",
  subtitle = "Common tasks for your current role.",
  items,
  chartData,
}: Props) {
  return (
    <div className="module-card">
      <div className="mc-head">
        <div className="mc-title">{title}</div>
        <div className="mc-sub">{subtitle}</div>
      </div>
      <div className="quick-grid">
        {items.map((item, i) => (
          <QuickActionTile key={i} title={item.title} sub={item.sub} onClick={item.onClick} />
        ))}
      </div>
      {chartData && <WeeklyBarChart data={chartData} />}
    </div>
  );
}
