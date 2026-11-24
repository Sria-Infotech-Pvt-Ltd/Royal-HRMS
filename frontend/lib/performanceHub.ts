// Pure helpers for the HR Performance hub: where each review is in the process, filtering, and how far a cycle has run.
// No component state, so everything here is unit-tested and safe to import anywhere.

import { tr } from "@/lib/i18n/tr"
import type { ApiCycle, ApiReview } from "@/types/performanceHub"

/** The steps a review passes through, in order. */
export type ReviewStage = "not_started" | "awaiting_manager" | "awaiting_calibration" | "awaiting_publish" | "published" | "acknowledged"
/** "needs_hr" is every review that is waiting for HR to calibrate or publish it. */
export type StageFilter = "" | ReviewStage | "needs_hr"

export interface StageMeta { key: ReviewStage; label: string; short: string; tone: "neutral" | "warn" | "info" | "success"; icon: string }

export const STAGES: StageMeta[] = [
  { key: "not_started",          label: "Self review not submitted", short: "Not started",    tone: "neutral", icon: "ti-user-edit" },
  { key: "awaiting_manager",     label: "Waiting for the manager",   short: "With manager",   tone: "warn",    icon: "ti-user-check" },
  { key: "awaiting_calibration", label: "Waiting for HR calibration", short: "To calibrate",  tone: "warn",    icon: "ti-scale" },
  { key: "awaiting_publish",     label: "Calibrated, ready to publish", short: "To publish",  tone: "info",    icon: "ti-send" },
  { key: "published",            label: "Published to the employee", short: "Published",      tone: "info",    icon: "ti-eye" },
  { key: "acknowledged",         label: "Acknowledged by the employee", short: "Acknowledged", tone: "success", icon: "ti-circle-check" },
]

type Progress = Pick<ApiReview, "self_submitted_at" | "manager_submitted_at" | "hr_calibrated_at" | "published_at" | "acknowledged_at">

/** Which step a review is at, read from the dates it has so far. */
export function reviewStage(review: Progress): ReviewStage {
  if (review.acknowledged_at) return "acknowledged"
  if (review.published_at) return "published"
  if (review.hr_calibrated_at) return "awaiting_publish"
  if (review.manager_submitted_at) return "awaiting_calibration"
  if (review.self_submitted_at) return "awaiting_manager"
  return "not_started"
}

export type StageCounts = Record<ReviewStage, number> & { total: number }

export function stageCounts(reviews: Progress[]): StageCounts {
  const counts: StageCounts = { not_started: 0, awaiting_manager: 0, awaiting_calibration: 0, awaiting_publish: 0, published: 0, acknowledged: 0, total: reviews.length }
  for (const review of reviews) counts[reviewStage(review)] += 1
  return counts
}

/** Reviews that need HR to do something now: calibrate, or publish. */
export const needsHr = (stage: ReviewStage): boolean => stage === "awaiting_calibration" || stage === "awaiting_publish"

/** What HR can do to this review next, matching the buttons on each row. */
export type RowAction = "review" | "calibrate" | "publish" | null
export function nextAction(review: Progress): RowAction {
  if (review.self_submitted_at && !review.manager_submitted_at) return "review"
  if (review.manager_submitted_at && !review.hr_calibrated_at) return "calibrate"
  if (review.hr_calibrated_at && !review.published_at) return "publish"
  return null
}

export const percentOf = (done: number, total: number): number => (total <= 0 ? 0 : Math.min(100, Math.round((done / total) * 100)))

/** Reviews narrowed by search (employee name, code or manager) and by stage, in the order they came. */
export function filterReviews<Row extends Progress & Pick<ApiReview, "employee_name" | "employee_code" | "manager_name">>(
  reviews: Row[], search: string, stage: StageFilter,
): Row[] {
  const needle = search.trim().toLowerCase()
  return reviews.filter(review => {
    const current = reviewStage(review)
    const stageMatches = stage === "" || (stage === "needs_hr" ? needsHr(current) : current === stage)
    const textMatches = needle === "" || [review.employee_name, review.employee_code, review.manager_name].some(value => (value ?? "").toLowerCase().includes(needle))
    return stageMatches && textMatches
  })
}

export const hasActiveFilters = (search: string, stage: StageFilter): boolean => search.trim() !== "" || stage !== ""

// ── Cycle dates ──────────────────────────────────────────────────────────────

const DAY_MS = 24 * 60 * 60 * 1000

/** "2026-11-30" as that day at local midnight; null for anything that is not a date. */
export function parseDay(value: string | null | undefined): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? "")
  if (!match) return null
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return Number.isNaN(date.getTime()) ? null : date
}

export const startOfDay = (date: Date): Date => new Date(date.getFullYear(), date.getMonth(), date.getDate())

/** Whole days from `from` to `to` (negative when `to` is earlier). */
export function daysBetween(from: Date, to: Date): number {
  return Math.round((startOfDay(to).getTime() - startOfDay(from).getTime()) / DAY_MS)
}

export interface Milestone { key: "start" | "self" | "manager" | "end"; label: string; date: string; percent: number; state: "done" | "next" | "later" }
export interface CycleProgress {
  /** How far through the period today is, 0 to 100. */
  percent: number
  phase: "upcoming" | "running" | "ended"
  /** Days until the period ends (running or upcoming), or 0 once it has ended. */
  daysLeft: number
  milestones: Milestone[]
}

/** How far a cycle has run, and where its due dates fall along the period. Null if the dates are unusable. */
export function cycleProgress(cycle: Pick<ApiCycle, "period_start" | "period_end" | "self_review_due" | "manager_review_due">, today: Date): CycleProgress | null {
  const start = parseDay(cycle.period_start)
  const end = parseDay(cycle.period_end)
  if (!start || !end || end <= start) return null
  const span = daysBetween(start, end)
  const place = (date: Date) => Math.min(100, Math.max(0, (daysBetween(start, date) / span) * 100))
  const now = startOfDay(today)
  const entries: { key: Milestone["key"]; label: string; value: string }[] = [
    { key: "start", label: "Period starts", value: cycle.period_start },
    { key: "self", label: "Self reviews due", value: cycle.self_review_due },
    { key: "manager", label: "Manager reviews due", value: cycle.manager_review_due },
    { key: "end", label: "Period ends", value: cycle.period_end },
  ]
  const dated = entries.map(entry => ({ ...entry, day: parseDay(entry.value) })).filter((entry): entry is typeof entry & { day: Date } => entry.day !== null)
  const nextKey = dated.find(entry => entry.day >= now)?.key
  const milestones: Milestone[] = dated.map(entry => ({
    key: entry.key, label: entry.label, date: entry.value, percent: place(entry.day),
    state: entry.day < now ? "done" : entry.key === nextKey ? "next" : "later",
  }))
  const phase = now < start ? "upcoming" : now > end ? "ended" : "running"
  return { percent: place(now), phase, daysLeft: phase === "ended" ? 0 : Math.max(0, daysBetween(now, end)), milestones }
}

/** True when the self-review deadline has passed and this person has still not submitted. */
export function isSelfReviewOverdue(review: Pick<ApiReview, "self_submitted_at">, cycle: Pick<ApiCycle, "self_review_due"> | null, today: Date): boolean {
  const due = parseDay(cycle?.self_review_due)
  return !!due && !review.self_submitted_at && startOfDay(today) > due
}

/** A short phrase for how close a date is: "today", "in 3 days", "5 days ago". */
export function relativeDay(value: string, today: Date): string {
  const day = parseDay(value)
  if (!day) return ""
  const diff = daysBetween(today, day)
  if (diff === 0) return tr("today")
  if (diff === 1) return tr("tomorrow")
  if (diff === -1) return tr("yesterday")
  return diff > 0 ? tr("in {count} days", { count: diff }) : tr("{count} days ago", { count: -diff })
}
