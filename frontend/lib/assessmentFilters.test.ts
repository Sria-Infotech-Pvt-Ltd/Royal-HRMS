import { describe, expect, it } from "vitest"
import {
  attemptsLabel, completionPercent, filterAssessments, hasActiveFilters, progressParts, summarize, timeLimitLabel,
} from "./assessmentFilters"

const row = (title: string, over: Partial<Record<string, unknown>> = {}) => ({
  title, description: "", is_active: true, created_at: "2026-11-01T00:00:00Z",
  assigned_count: 0, pending_count: 0, in_progress_count: 0, completed_count: 0, ...over,
}) as Parameters<typeof filterAssessments>[0][number]

describe("assessment helpers", () => {
  it("works out completion as a whole percentage, and zero when nobody is assigned", () => {
    expect(completionPercent({ assigned_count: 8, completed_count: 2 })).toBe(25)
    expect(completionPercent({ assigned_count: 3, completed_count: 2 })).toBe(67)
    expect(completionPercent({ assigned_count: 0, completed_count: 0 })).toBe(0)
    expect(completionPercent({ assigned_count: 2, completed_count: 9 })).toBe(100)
  })

  it("totals every assessment and counts the active ones", () => {
    const totals = summarize([
      row("A", { assigned_count: 10, pending_count: 4, in_progress_count: 2, completed_count: 4 }),
      row("B", { assigned_count: 10, completed_count: 6, is_active: false }),
    ])
    expect(totals).toEqual({ assessments: 2, active: 1, assigned: 20, pending: 4, inProgress: 2, completed: 10, completionRate: 50 })
    expect(summarize([])).toMatchObject({ assessments: 0, assigned: 0, completionRate: 0 })
  })

  it("treats a missing or odd count as zero", () => {
    expect(summarize([row("A", { assigned_count: undefined, completed_count: "x" })]).assigned).toBe(0)
  })

  it("splits the progress bar into done, in progress and not started", () => {
    expect(progressParts({ assigned_count: 10, completed_count: 5, in_progress_count: 3, pending_count: 2 })).toEqual({ completed: 50, inProgress: 30, pending: 20 })
    expect(progressParts({ assigned_count: 0, completed_count: 0, in_progress_count: 0, pending_count: 0 })).toEqual({ completed: 0, inProgress: 0, pending: 0 })
  })

  it("words attempts and time limits, marking the ones inherited from the global setting", () => {
    expect(attemptsLabel({ effective_max_attempts: 0, max_attempts: 0 })).toBe("Unlimited attempts")
    expect(attemptsLabel({ effective_max_attempts: 1, max_attempts: 1 })).toBe("1 attempt")
    expect(attemptsLabel({ effective_max_attempts: 3, max_attempts: null })).toBe("3 attempts (global)")
    expect(timeLimitLabel({ effective_time_limit_mins: null, time_limit_mins: null })).toBe("No time limit")
    expect(timeLimitLabel({ effective_time_limit_mins: 30, time_limit_mins: 30 })).toBe("30 min")
    expect(timeLimitLabel({ effective_time_limit_mins: 45, time_limit_mins: null })).toBe("45 min (global)")
  })

  it("searches title and description without caring about case", () => {
    const rows = [row("Safety Basics", { description: "Fire drills" }), row("Code of Conduct")]
    expect(filterAssessments(rows, "  SAFETY ", "", "title").map(item => item.title)).toEqual(["Safety Basics"])
    expect(filterAssessments(rows, "fire", "", "title").map(item => item.title)).toEqual(["Safety Basics"])
    expect(filterAssessments(rows, "zzz", "", "title")).toEqual([])
  })

  it("filters by active or inactive", () => {
    const rows = [row("A"), row("B", { is_active: false })]
    expect(filterAssessments(rows, "", "active", "title").map(item => item.title)).toEqual(["A"])
    expect(filterAssessments(rows, "", "inactive", "title").map(item => item.title)).toEqual(["B"])
  })

  it("sorts as asked and never changes the list it was given", () => {
    const rows = [
      row("B", { created_at: "2026-11-02T00:00:00Z", assigned_count: 5, pending_count: 1 }),
      row("A", { created_at: "2026-11-01T00:00:00Z", assigned_count: 9, pending_count: 6, in_progress_count: 1 }),
      row("C", { created_at: "2026-11-03T00:00:00Z", assigned_count: 1 }),
    ]
    const original = [...rows]
    const titles = (sort: Parameters<typeof filterAssessments>[3]) => filterAssessments(rows, "", "", sort).map(item => item.title)
    expect(titles("newest")).toEqual(["C", "B", "A"])
    expect(titles("title")).toEqual(["A", "B", "C"])
    expect(titles("most_assigned")).toEqual(["A", "B", "C"])
    expect(titles("needs_attention")).toEqual(["A", "B", "C"])
    expect(rows).toEqual(original)
  })

  it("reports a filter as active only when something narrows the list", () => {
    expect(hasActiveFilters("", "")).toBe(false)
    expect(hasActiveFilters("  ", "")).toBe(false)
    expect(hasActiveFilters("a", "")).toBe(true)
    expect(hasActiveFilters("", "inactive")).toBe(true)
  })
})
