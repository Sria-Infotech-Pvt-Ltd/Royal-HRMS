// Pure helpers for the Assessment Management page: no component state, safe to import anywhere.

import type { Assessment } from "@/app/dashboard/assessments/_types"

export type StateFilter = "" | "active" | "inactive"
export type SortKey = "newest" | "title" | "most_assigned" | "needs_attention"

export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "newest",          label: "Newest first" },
  { value: "title",           label: "Title (A to Z)" },
  { value: "most_assigned",   label: "Most assigned" },
  { value: "needs_attention", label: "Needs attention" },
]

type Counted = Pick<Assessment, "assigned_count" | "pending_count" | "in_progress_count" | "completed_count">

const count = (value: number | undefined | null) => (typeof value === "number" && Number.isFinite(value) ? value : 0)

/** Whole-number percentage of assigned people who have finished, 0 when nobody is assigned. */
export function completionPercent(assessment: Pick<Assessment, "assigned_count" | "completed_count">): number {
  const assigned = count(assessment.assigned_count)
  if (assigned <= 0) return 0
  return Math.min(100, Math.round((count(assessment.completed_count) / assigned) * 100))
}

export interface AssessmentTotals {
  assessments: number
  active:      number
  assigned:    number
  pending:     number
  inProgress:  number
  completed:   number
  /** Share of everything assigned that is finished, as a whole number. */
  completionRate: number
}

export function summarize(assessments: (Counted & Pick<Assessment, "is_active">)[]): AssessmentTotals {
  const sum = (pick: (item: Counted) => number | undefined) => assessments.reduce((total, item) => total + count(pick(item)), 0)
  const assigned = sum(item => item.assigned_count)
  const completed = sum(item => item.completed_count)
  return {
    assessments: assessments.length,
    active: assessments.filter(item => item.is_active).length,
    assigned,
    pending: sum(item => item.pending_count),
    inProgress: sum(item => item.in_progress_count),
    completed,
    completionRate: assigned > 0 ? Math.min(100, Math.round((completed / assigned) * 100)) : 0,
  }
}

/** The widths (as whole percentages of the assigned people) of the progress bar's three parts: done, in progress, not started. */
export function progressParts(assessment: Counted): { completed: number; inProgress: number; pending: number } {
  const assigned = count(assessment.assigned_count)
  if (assigned <= 0) return { completed: 0, inProgress: 0, pending: 0 }
  const share = (value: number | undefined) => Math.min(100, (count(value) / assigned) * 100)
  return { completed: share(assessment.completed_count), inProgress: share(assessment.in_progress_count), pending: share(assessment.pending_count) }
}

export function attemptsLabel(assessment: Pick<Assessment, "effective_max_attempts" | "max_attempts">): string {
  const attempts = assessment.effective_max_attempts === 0 ? "Unlimited attempts" : `${assessment.effective_max_attempts} attempt${assessment.effective_max_attempts !== 1 ? "s" : ""}`
  return assessment.max_attempts == null ? `${attempts} (global)` : attempts
}

export function timeLimitLabel(assessment: Pick<Assessment, "effective_time_limit_mins" | "time_limit_mins">): string {
  if (!assessment.effective_time_limit_mins) return "No time limit"
  const minutes = `${assessment.effective_time_limit_mins} min`
  return assessment.time_limit_mins == null ? `${minutes} (global)` : minutes
}

/** Assessments narrowed by search (title or description) and active/inactive, then sorted. The input list is not changed. */
export function filterAssessments<Row extends Counted & Pick<Assessment, "title" | "description" | "is_active" | "created_at">>(
  rows: Row[], search: string, state: StateFilter, sort: SortKey,
): Row[] {
  const needle = search.trim().toLowerCase()
  const matches = (row: Row) =>
    (state === "" || (state === "active") === row.is_active) &&
    (needle === "" || row.title.toLowerCase().includes(needle) || (row.description ?? "").toLowerCase().includes(needle))
  const attention = (row: Row) => count(row.pending_count) + count(row.in_progress_count)
  const compare: Record<SortKey, (first: Row, second: Row) => number> = {
    newest:          (first, second) => (second.created_at ?? "").localeCompare(first.created_at ?? ""),
    title:           (first, second) => first.title.localeCompare(second.title),
    most_assigned:   (first, second) => count(second.assigned_count) - count(first.assigned_count),
    needs_attention: (first, second) => attention(second) - attention(first),
  }
  return rows.filter(matches).sort((first, second) => compare[sort](first, second) || first.title.localeCompare(second.title))
}

export function hasActiveFilters(search: string, state: StateFilter): boolean {
  return search.trim() !== "" || state !== ""
}
