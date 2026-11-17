"use client";

import type { AssessmentTotals } from "@/lib/assessmentFilters";

interface AssessmentStatsProps {
  totals:    AssessmentTotals
  isLoading: boolean
}

/** Four headline numbers, each with one line of context. Dashes while loading. */
export default function AssessmentStats({ totals, isLoading }: AssessmentStatsProps) {
  const cards = [
    { label: "Assessments", value: totals.assessments, icon: "ti-clipboard-list", tone: "si-primary", sub: `${totals.active} active` },
    { label: "Assigned",    value: totals.assigned,    icon: "ti-users",          tone: "si-info",    sub: "Across all assessments" },
    { label: "In progress", value: totals.inProgress,  icon: "ti-pencil",         tone: "si-warn",    sub: `${totals.pending} not started yet` },
    { label: "Completed",   value: totals.completed,   icon: "ti-circle-check",   tone: "si-success", sub: totals.assigned > 0 ? `${totals.completionRate}% completion rate` : "Nothing assigned yet" },
  ];
  return (
    <div className="stats-grid">
      {cards.map(card => (
        <div key={card.label} className="stat-card">
          <div className={`stat-icon ${card.tone}`}><i className={`ti ${card.icon}`} /></div>
          <div className="stat-label">{card.label}</div>
          <div className="stat-value">{isLoading ? "—" : card.value.toLocaleString()}</div>
          <div className="stat-sub">{isLoading ? "Loading…" : card.sub}</div>
        </div>
      ))}
    </div>
  );
}
