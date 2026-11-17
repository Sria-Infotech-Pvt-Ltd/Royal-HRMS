"use client";

import { buildStatCards, type StatusFilter } from "./_filters";
import type { RecruitmentStats } from "./_data";

interface CandidateStatCardsProps {
  stats:        RecruitmentStats | null
  branchName?:  string
  /** The status the list is currently filtered to; its card is highlighted. */
  activeStatus: StatusFilter
  onSelect:     (status: StatusFilter) => void
}

/** The four summary numbers. Each card is a button: click one to filter the list to that status, click it again to clear. */
export default function CandidateStatCards({ stats, branchName, activeStatus, onSelect }: CandidateStatCardsProps) {
  return (
    <div className="stats-grid">
      {buildStatCards(stats, branchName).map(card => {
        const isActive = card.key !== "" && activeStatus === card.key;
        return (
          <button
            key={card.label}
            type="button"
            className={`stat-card cand-stat${isActive ? " is-active" : ""}`}
            aria-pressed={isActive}
            title={card.key === "" ? "Show every candidate" : isActive ? `Showing ${card.label.toLowerCase()} only. Click to clear.` : `Show ${card.label.toLowerCase()} candidates`}
            onClick={() => onSelect(isActive ? "" : card.key)}
          >
            <div className={`stat-icon ${card.tone}`}><i className={`ti ${card.icon}`} /></div>
            <div className="stat-label">{card.label}</div>
            <div className="stat-value">{card.value === null ? "—" : card.value.toLocaleString()}</div>
            <div className="stat-sub">{card.sub}</div>
          </button>
        );
      })}
    </div>
  );
}
