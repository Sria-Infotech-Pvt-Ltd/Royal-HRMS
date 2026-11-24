"use client";

import { ApprovalKind, DisplayStatus, STATUS_FILTERS, TYPE_BADGE } from "../_data";
import DateInput from "@/components/shared/DateInput";
import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";

interface Props {
  search:        string;
  onSearch:      (v: string) => void;
  status:        "all" | DisplayStatus;
  onStatus:      (v: "all" | DisplayStatus) => void;
  showTypeFilter: boolean;
  type:          "all" | ApprovalKind;
  onType:        (v: "all" | ApprovalKind) => void;
  dateFrom:      string;
  onDateFrom:    (v: string) => void;
  dateTo:        string;
  onDateTo:      (v: string) => void;
  onRefresh:     () => void;
  refreshing:    boolean;
}

function toIso(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/** Quick "submitted between" ranges: [label, from, to] for today, the last 7 days and this month. */
function datePresets(): { label: string; from: string; to: string }[] {
  const today = new Date();
  const weekAgo = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 6);
  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
  return [
    { label: tr("Today"),        from: toIso(today),      to: toIso(today) },
    { label: tr("Last 7 days"),  from: toIso(weekAgo),    to: toIso(today) },
    { label: tr("This month"),   from: toIso(monthStart), to: toIso(today) },
  ];
}

export default function ApprovalsToolbar({
  search, onSearch, status, onStatus, showTypeFilter, type, onType,
  dateFrom, onDateFrom, dateTo, onDateTo, onRefresh, refreshing,
}: Props) {
  const t = useT();
  const presets = datePresets();
  const hasActiveFilters = search !== "" || status !== "pending" || type !== "all" || dateFrom !== "" || dateTo !== "";
  function clearFilters() {
    onSearch("");
    onStatus("pending");
    onType("all");
    onDateFrom("");
    onDateTo("");
  }
  return (
    <>
    <div className="ta-toolbar">
      <div className="ta-search-box">
        <i className="ti ti-search" />
        <input
          type="text"
          placeholder={t("Search employee name or ID…")}
          value={search}
          onChange={e => onSearch(e.target.value)}
          suppressHydrationWarning
        />
      </div>

      <select
        className="ta-filter-select"
        value={status}
        onChange={e => onStatus(e.target.value as "all" | DisplayStatus)}
        suppressHydrationWarning
      >
        {STATUS_FILTERS.map(s => <option key={s.key} value={s.key}>{t(s.label)}</option>)}
      </select>

      {showTypeFilter && (
        <select
          className="ta-filter-select"
          value={type}
          onChange={e => onType(e.target.value as "all" | ApprovalKind)}
          suppressHydrationWarning
        >
          <option value="all">{t("All Types")}</option>
          {(Object.keys(TYPE_BADGE) as ApprovalKind[]).map(k => (
            <option key={k} value={k}>{t(TYPE_BADGE[k].label)}</option>
          ))}
        </select>
      )}

      <DateInput className="ta-date-input" value={dateFrom} onChange={isoDate => onDateFrom(isoDate)} title={t("Submitted from")} />
      <span style={{ fontSize: 12, color: "var(--ta-text-faint)" }}>{t("to")}</span>
      <DateInput className="ta-date-input" value={dateTo} onChange={isoDate => onDateTo(isoDate)} title={t("Submitted to")} />

      <button className="ta-refresh-btn" onClick={onRefresh} disabled={refreshing} suppressHydrationWarning>
        <i className={`ti ti-refresh ${refreshing ? "spin" : ""}`} />
        {t("Refresh")}
      </button>
    </div>
    <div className="tv-chips">
      <span className="tv-chips-label">{t("Submitted:")}</span>
      {presets.map(preset => (
        <button
          key={preset.label}
          type="button"
          className={`tv-chip${dateFrom === preset.from && dateTo === preset.to ? " is-on" : ""}`}
          onClick={() => { onDateFrom(preset.from); onDateTo(preset.to); }}
        >
          {preset.label}
        </button>
      ))}
      {hasActiveFilters && (
        <button type="button" className="tv-chip is-clear" onClick={clearFilters}><i className="ti ti-filter-off" /> {t("Clear filters")}</button>
      )}
    </div>
    </>
  );
}
