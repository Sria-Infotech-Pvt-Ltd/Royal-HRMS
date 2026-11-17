"use client";

import type { QueueCounts, QueueStatusFilter } from "@/types/onboardingQueue";
import { buildApprovalCards } from "./_filters";

interface ApprovalStatCardsProps {
  counts:       QueueCounts
  activeStatus: QueueStatusFilter
  onSelect:     (status: QueueStatusFilter) => void
}

/** The summary numbers. Each card is a button: click one to filter the list, click it again to clear. */
export default function ApprovalStatCards({ counts, activeStatus, onSelect }: ApprovalStatCardsProps) {
  return (
    <div className="stats-grid">
      {buildApprovalCards(counts).map(card => {
        const isActive = card.key !== "" && activeStatus === card.key;
        return (
          <button
            key={card.label}
            type="button"
            className={`stat-card cand-stat${isActive ? " is-active" : ""}`}
            aria-pressed={isActive}
            title={card.key === "" ? "Show every submission" : isActive ? "Click to clear this filter" : `Show only: ${card.label.toLowerCase()}`}
            onClick={() => onSelect(isActive ? "" : card.key)}
          >
            <div className={`stat-icon ${card.tone}`}><i className={`ti ${card.icon}`} /></div>
            <div className="stat-label">{card.label}</div>
            <div className="stat-value">{card.value.toLocaleString()}</div>
            <div className="stat-sub">{card.sub}</div>
          </button>
        );
      })}
    </div>
  );
}
