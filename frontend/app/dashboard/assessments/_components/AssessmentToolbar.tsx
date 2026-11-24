"use client";

import { SORT_OPTIONS, type SortKey, type StateFilter } from "@/lib/assessmentFilters";

import { useT } from "@/hooks/useI18n";

interface AssessmentToolbarProps {
  search:     string
  onSearch:   (text: string) => void
  state:      StateFilter
  onState:    (state: StateFilter) => void
  sort:       SortKey
  onSort:     (sort: SortKey) => void
  /** Assessments showing / assessments in total, for the summary line. */
  shown:      number
  total:      number
  hasFilters: boolean
  onClear:    () => void
}

const STATE_LABEL: Record<Exclude<StateFilter, "">, string> = { active: "Active", inactive: "Inactive" };

/** Search, an active/inactive pick and a sort in one row, with removable chips and a count when something is filtered. */
export default function AssessmentToolbar(props: AssessmentToolbarProps) {
  const t = useT();
  const { search, state, sort, shown, total, hasFilters } = props;
  return (
    <div className="card cand-toolbar">
      <div className="cand-toolbar-row">
        <div className="cand-search">
          <i className="ti ti-search" aria-hidden="true" />
          <input
            type="search" className="field-input" placeholder={t("Search assessments by title or description")}
            aria-label={t("Search assessments")} value={search} maxLength={100}
            onChange={event => props.onSearch(event.target.value)} suppressHydrationWarning
          />
          {search && (
            <button type="button" className="cand-search-clear" aria-label={t("Clear search")} onClick={() => props.onSearch("")}>
              <i className="ti ti-x" />
            </button>
          )}
        </div>
        <label className="cand-select">
          <i className="ti ti-filter" aria-hidden="true" />
          <span className="sr-only">{t("Status")}</span>
          <select className="field-input field-select" value={state} onChange={event => props.onState(event.target.value as StateFilter)} suppressHydrationWarning>
            <option value="">{t("All assessments")}</option>
            <option value="active">{t("Active")}</option>
            <option value="inactive">{t("Inactive")}</option>
          </select>
        </label>
        <label className="cand-select">
          <i className="ti ti-arrows-sort" aria-hidden="true" />
          <span className="sr-only">{t("Sort assessments")}</span>
          <select className="field-input field-select" value={sort} onChange={event => props.onSort(event.target.value as SortKey)} suppressHydrationWarning>
            {SORT_OPTIONS.map(option => <option key={option.value} value={option.value}>{t(option.label)}</option>)}
          </select>
        </label>
      </div>

      {hasFilters && (
        <div className="cand-chips" aria-label={t("Active filters")}>
          <span className="cand-chips-label" role="status">{t("Showing {shown} of {total}", { shown, total })}</span>
          {search.trim() && (
            <span className="cand-chip">“{search.trim()}”
              <button type="button" aria-label={t("Remove search filter")} onClick={() => props.onSearch("")}><i className="ti ti-x" aria-hidden="true" /></button>
            </span>
          )}
          {state && (
            <span className="cand-chip">{t(STATE_LABEL[state])}
              <button type="button" aria-label={t("Remove status filter")} onClick={() => props.onState("")}><i className="ti ti-x" aria-hidden="true" /></button>
            </span>
          )}
          <button type="button" className="btn-link" onClick={props.onClear}>{t("Clear all")}</button>
        </div>
      )}
    </div>
  );
}
