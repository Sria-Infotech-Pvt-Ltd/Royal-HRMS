"use client";

// The "<Section> overview" left-hand card — bold heading, gray subtitle,
// then a divider-separated list of OverviewRow entries. Extracted so a
// module's page.tsx only supplies data, not markup.

import { OverviewRow } from "./ModuleOverviewKit";

export interface OverviewListItem {
  label: string;
  sub: string;
  chip: string;
  chipTone: "warn" | "error" | "success";
  onOpen: () => void;
}

interface Props {
  title: string;
  subtitle?: string;
  items: OverviewListItem[];
  emptyIcon?: string;
  emptyTitle?: string;
}

export default function OverviewList({
  title,
  subtitle = "Current records and items requiring attention.",
  items,
  emptyIcon = "ti-list-check",
  emptyTitle = "Nothing to show yet",
}: Props) {
  return (
    <div className="module-card">
      <div className="mc-head">
        <div className="mc-title">{title}</div>
        <div className="mc-sub">{subtitle}</div>
      </div>
      <div style={{ padding: "0 20px 4px" }}>
        {items.length === 0 ? (
          <div className="empty-state"><i className={`ti ${emptyIcon}`} /><h3>{emptyTitle}</h3></div>
        ) : items.map((row, i) => (
          <OverviewRow
            key={i}
            label={row.label}
            sub={row.sub}
            chip={row.chip}
            chipTone={row.chipTone}
            onOpen={row.onOpen}
          />
        ))}
      </div>
    </div>
  );
}
