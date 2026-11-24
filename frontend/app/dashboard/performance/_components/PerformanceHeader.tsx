"use client";

import { useT } from "@/hooks/useI18n";

export type HubTab = "overview" | "queue" | "cycles"

interface PerformanceHeaderProps {
  tab:         HubTab
  onTab:       (tab: HubTab) => void
  onBack:      () => void
  /** Reviews waiting for HR to calibrate or publish: shown as a badge on the queue tab. */
  needsHrCount: number
  cycleCount:  number
}

const TABS: { key: HubTab; label: string; icon: string }[] = [
  { key: "overview", label: "Overview",     icon: "ti-layout-dashboard" },
  { key: "queue",    label: "Review queue", icon: "ti-list-check" },
  { key: "cycles",   label: "Cycles",       icon: "ti-calendar-time" },
]

/** Title, Back, and the three sections of the hub. (New cycles are created from the Overview and Cycles tabs, not from here.) */
export default function PerformanceHeader({ tab, onTab, onBack, needsHrCount, cycleCount }: PerformanceHeaderProps) {
  const t = useT();
  const badge = (key: HubTab) => (key === "queue" ? needsHrCount : key === "cycles" ? cycleCount : 0);
  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">{t("Performance reviews")}</div>
          <div className="page-sub">{t("Run review cycles and follow every review from self-assessment to publication.")}</div>
        </div>
        <div className="page-actions">
          <button type="button" className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> {t("Back")}</button>
        </div>
      </div>

      <div className="perf-tabs" role="tablist" aria-label={t("Performance sections")}>
        {TABS.map(item => (
          <button
            key={item.key} type="button" role="tab" id={`perf-tab-${item.key}`} aria-selected={tab === item.key} aria-controls="perf-panel"
            className={`perf-tab${tab === item.key ? " on" : ""}`} onClick={() => onTab(item.key)}
          >
            <i className={`ti ${item.icon}`} /> {t(item.label)}
            {badge(item.key) > 0 && <span className={`perf-tab-badge${item.key === "queue" ? " attn" : ""}`}>{badge(item.key)}</span>}
          </button>
        ))}
      </div>
    </>
  );
}
