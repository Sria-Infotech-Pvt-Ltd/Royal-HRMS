"use client";

import type { AssessmentTotals } from "@/lib/assessmentFilters";
import { useT } from "@/hooks/useI18n";

interface AssessmentStatsProps {
  totals:    AssessmentTotals
  isLoading: boolean
}

/** Four headline numbers, each with one line of context. Dashes while loading. */
export default function AssessmentStats({ totals, isLoading }: AssessmentStatsProps) {
  const t = useT();
  const cards = [
    { label: "Assessments", value: totals.assessments, icon: "ti-clipboard-list", tone: "si-primary", sub: t("{count} active", { count: totals.active }) },
    { label: "Assigned",    value: totals.assigned,    icon: "ti-users",          tone: "si-info",    sub: t("Across all assessments") },
    { label: "In progress", value: totals.inProgress,  icon: "ti-pencil",         tone: "si-warn",    sub: t("{count} not started yet", { count: totals.pending }) },
    { label: "Completed",   value: totals.completed,   icon: "ti-circle-check",   tone: "si-success", sub: totals.assigned > 0 ? t("{rate}% completion rate", { rate: totals.completionRate }) : t("Nothing assigned yet") },
  ];
  return (
    <div className="stats-grid">
      {cards.map(card => (
        <div key={card.label} className="stat-card">
          <div className={`stat-icon ${card.tone}`}><i className={`ti ${card.icon}`} /></div>
          <div className="stat-label">{t(card.label)}</div>
          <div className="stat-value">{isLoading ? "—" : card.value.toLocaleString()}</div>
          <div className="stat-sub">{isLoading ? t("Loading…") : card.sub}</div>
        </div>
      ))}
    </div>
  );
}
