"use client";

import type { QueueCounts, QueueStatusFilter } from "@/types/onboardingQueue";
import { buildApprovalCards } from "./_filters";
import { useT } from "@/hooks/useI18n";

interface ApprovalStatCardsProps {
  counts:       QueueCounts
  activeStatus: QueueStatusFilter
  onSelect:     (status: QueueStatusFilter) => void
}

/** The summary numbers. Each card is a button: click one to filter the list, click it again to clear. */
export default function ApprovalStatCards({ counts, activeStatus, onSelect }: ApprovalStatCardsProps) {
  const t = useT();
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
            title={card.key === "" ? t("Show every submission") : isActive ? t("Click to clear this filter") : t("Show only: {label}", { label: t(card.label).toLowerCase() })}
            onClick={() => onSelect(isActive ? "" : card.key)}
          >
            <div className={`stat-icon ${card.tone}`}><i className={`ti ${card.icon}`} /></div>
            <div className="stat-label">{t(card.label)}</div>
            <div className="stat-value">{card.value.toLocaleString()}</div>
            <div className="stat-sub">{card.sub}</div>
          </button>
        );
      })}
    </div>
  );
}
