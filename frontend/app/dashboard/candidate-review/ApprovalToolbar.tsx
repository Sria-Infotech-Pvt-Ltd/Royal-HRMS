"use client";

import type { QueueStatus, QueueStatusFilter } from "@/types/onboardingQueue";
import { STATUS_META } from "./_filters";
import { useT } from "@/hooks/useI18n";

interface ApprovalToolbarProps {
  search:     string
  onSearch:   (text: string) => void
  status:     QueueStatusFilter
  onStatus:   (status: QueueStatusFilter) => void
  hasFilters: boolean
  onClear:    () => void
}

const STATUSES = Object.keys(STATUS_META) as QueueStatus[];

/** Search and a status pick in one row; when something is filtered, removable chips show what. */
export default function ApprovalToolbar({ search, onSearch, status, onStatus, hasFilters, onClear }: ApprovalToolbarProps) {
  const t = useT();
  return (
    <div className="card cand-toolbar">
      <div className="cand-toolbar-row">
        <div className="cand-search">
          <i className="ti ti-search" aria-hidden="true" />
          <input
            type="search"
            className="field-input"
            placeholder={t("Search by name, email or designation")}
            aria-label={t("Search submissions")}
            value={search}
            onChange={event => onSearch(event.target.value)}
            suppressHydrationWarning
          />
          {search && (
            <button type="button" className="cand-search-clear" aria-label={t("Clear search")} onClick={() => onSearch("")}>
              <i className="ti ti-x" />
            </button>
          )}
        </div>
        <label className="cand-select">
          <i className="ti ti-filter" aria-hidden="true" />
          <span className="sr-only">{t("Status")}</span>
          <select className="field-input field-select" value={status} onChange={event => onStatus(event.target.value as QueueStatusFilter)} suppressHydrationWarning>
            <option value="">{t("All statuses")}</option>
            {STATUSES.map(value => <option key={value} value={value}>{t(STATUS_META[value].label)}</option>)}
          </select>
        </label>
      </div>

      {hasFilters && (
        <div className="cand-chips" aria-label={t("Active filters")}>
          <span className="cand-chips-label">{t("Filtered by")}</span>
          {search.trim() && (
            <span className="cand-chip">“{search.trim()}”
              <button type="button" aria-label={t("Remove search filter")} onClick={() => onSearch("")}><i className="ti ti-x" aria-hidden="true" /></button>
            </span>
          )}
          {status && (
            <span className="cand-chip">{t(STATUS_META[status].label)}
              <button type="button" aria-label={t("Remove status filter")} onClick={() => onStatus("")}><i className="ti ti-x" aria-hidden="true" /></button>
            </span>
          )}
          <button type="button" className="btn-link" onClick={onClear}>{t("Clear all")}</button>
        </div>
      )}
    </div>
  );
}
