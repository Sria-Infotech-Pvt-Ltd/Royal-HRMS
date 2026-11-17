"use client";

import { FILTERS } from "./_data";
import { SORT_OPTIONS, type SortKey } from "./_filters";

interface AnnouncementToolbarProps {
  /** What is typed in the box right now (the list itself follows a moment later). */
  searchText:     string
  category:       string
  sort:           SortKey
  pinnedOnly:     boolean
  hasFilters:     boolean
  /** Posts on this page / posts matching the current filters; null until the first load. */
  shown:          number | null
  matching:       number | null
  onSearchText:   (text: string) => void
  onCategory:     (category: string) => void
  onSort:         (sort: SortKey) => void
  onPinnedOnly:   (pinnedOnly: boolean) => void
  onClear:        () => void
}

/** Search, category pills, pinned-only switch and sort, with a one-line summary of what is showing. */
export default function AnnouncementToolbar(props: AnnouncementToolbarProps) {
  const { searchText, category, sort, pinnedOnly, hasFilters, shown, matching } = props

  return (
    <div className="ann-toolbar-block">
      <div className="ann-toolbar">
        <div className="ann-search">
          <i className="ti ti-search" aria-hidden="true" />
          <input
            type="search"
            className="field-input"
            placeholder="Search title or message"
            aria-label="Search announcements"
            value={searchText}
            maxLength={100}
            onChange={event => props.onSearchText(event.target.value)}
            suppressHydrationWarning
          />
          {searchText && (
            <button type="button" className="ann-search-clear" aria-label="Clear search" onClick={() => props.onSearchText("")}>
              <i className="ti ti-x" />
            </button>
          )}
        </div>

        <button
          type="button"
          className={`ann-chip${pinnedOnly ? " on" : ""}`}
          aria-pressed={pinnedOnly}
          onClick={() => props.onPinnedOnly(!pinnedOnly)}
        >
          <i className="ti ti-pin" aria-hidden="true" /> Pinned only
        </button>

        <label className="ann-sort">
          <span className="sr-only">Sort announcements</span>
          <select
            className="field-input field-select"
            value={sort}
            onChange={event => props.onSort(event.target.value as SortKey)}
          >
            {SORT_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
      </div>

      <div className="ann-filter-bar">
        {FILTERS.map(filter => (
          <button
            key={filter.value}
            type="button"
            onClick={() => props.onCategory(filter.value)}
            className={`btn ${category === filter.value ? "btn-filled" : "btn-ghost"}`}
            suppressHydrationWarning
          >
            {filter.label}
          </button>
        ))}
      </div>

      {(shown !== null && matching !== null && (matching > 0 || hasFilters)) && (
        <div className="ann-summary" role="status">
          <span>{matching === 0 ? "No posts match" : `Showing ${shown} of ${matching} ${matching === 1 ? "post" : "posts"}`}</span>
          {hasFilters && (
            <button type="button" className="btn-link" onClick={props.onClear}>
              <i className="ti ti-filter-off" aria-hidden="true" /> Clear filters
            </button>
          )}
        </div>
      )}
    </div>
  )
}
