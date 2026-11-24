"use client";

import { useT } from "@/hooks/useI18n";
import { STAGES, percentOf, type ReviewStage, type StageCounts } from "@/lib/performanceHub";

interface StageFunnelProps {
  counts:   StageCounts
  onSelect: (stage: ReviewStage) => void
}

/** Where every review in the active cycle is right now. Click a step to list exactly those reviews. */
export default function StageFunnel({ counts, onSelect }: StageFunnelProps) {
  const t = useT();
  if (counts.total === 0) {
    return <p className="perf-muted">{t("No reviews yet. They appear here as employees open their Appraisals tab.")}</p>;
  }
  return (
    <ul className="perf-funnel" aria-label={t("Reviews by step")}>
      {STAGES.map(stage => {
        const value = counts[stage.key];
        return (
          <li key={stage.key}>
            <button type="button" className="perf-funnel-row" onClick={() => onSelect(stage.key)} disabled={value === 0} title={t(stage.label)}>
              <span className="perf-funnel-label"><i className={`ti ${stage.icon}`} /> {t(stage.short)}</span>
              <span className="perf-funnel-bar"><span className={`tone-${stage.tone}`} style={{ width: `${percentOf(value, counts.total)}%` }} /></span>
              <span className="perf-funnel-count">{value}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
