// Pure helpers for the Announcements list filters: no component state, safe to import anywhere.

import { tr } from "@/lib/i18n/tr"

export type SortKey = "newest" | "oldest" | "reactions" | "views"

export interface ListFilters {
  /** "" = every category. */
  category:   string
  /** Already trimmed and debounced. */
  search:     string
  pinnedOnly: boolean
  sort:       SortKey
}

export const SORT_OPTIONS: ReadonlyArray<{ value: SortKey; label: string }> = [
  { value: "newest",    label: "Newest first"   },
  { value: "oldest",    label: "Oldest first"   },
  { value: "reactions", label: "Most reactions" },
  { value: "views",     label: "Most views"     },
]

export const DEFAULT_SORT: SortKey = "newest"

/** The query string for one page of the list. Options at their default are left out, so a plain request stays a plain request. */
export function buildListParams(filters: ListFilters, page: number, pageSize = 10): Record<string, string> {
  const params: Record<string, string> = { page: String(page), page_size: String(pageSize) }
  if (filters.category) params.category = filters.category
  if (filters.search) params.search = filters.search
  if (filters.pinnedOnly) params.pinned = "1"
  if (filters.sort !== DEFAULT_SORT) params.sort = filters.sort
  return params
}

/** True when anything narrows the list: a category, a search, the pinned switch or a non-default sort. */
export function hasActiveFilters(filters: ListFilters): boolean {
  return Boolean(filters.category || filters.search || filters.pinnedOnly || filters.sort !== DEFAULT_SORT)
}

/** "about 3 per post", or null when there are no posts to average over. */
export function averagePerPost(total: number, posts: number): string | null {
  if (posts <= 0) return null
  const average = total / posts
  return tr("about {count} per post", { count: average >= 10 ? Math.round(average) : Math.round(average * 10) / 10 })
}
