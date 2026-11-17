import { describe, expect, it } from "vitest"
import {
  cycleProgress, daysBetween, filterReviews, hasActiveFilters, isSelfReviewOverdue, needsHr, nextAction, parseDay, percentOf,
  relativeDay, reviewStage, stageCounts,
} from "./performanceHub"

const review = (over: Record<string, string | null> = {}) => ({
  employee_name: "Asha Verma", employee_code: "EMP1", manager_name: "Ravi Kumar",
  self_submitted_at: null, manager_submitted_at: null, hr_calibrated_at: null, published_at: null, acknowledged_at: null, ...over,
})
const T = "2026-11-01T10:00:00Z"
const cycle = { period_start: "2026-10-01", period_end: "2026-12-31", self_review_due: "2026-11-15", manager_review_due: "2026-12-01" }
const day = (iso: string) => parseDay(iso) as Date

describe("where a review is", () => {
  it("reads the step from the dates it has so far", () => {
    expect(reviewStage(review())).toBe("not_started")
    expect(reviewStage(review({ self_submitted_at: T }))).toBe("awaiting_manager")
    expect(reviewStage(review({ self_submitted_at: T, manager_submitted_at: T }))).toBe("awaiting_calibration")
    expect(reviewStage(review({ self_submitted_at: T, manager_submitted_at: T, hr_calibrated_at: T }))).toBe("awaiting_publish")
    expect(reviewStage(review({ self_submitted_at: T, manager_submitted_at: T, hr_calibrated_at: T, published_at: T }))).toBe("published")
    expect(reviewStage(review({ self_submitted_at: T, manager_submitted_at: T, hr_calibrated_at: T, published_at: T, acknowledged_at: T }))).toBe("acknowledged")
  })

  it("counts reviews at each step and in total", () => {
    const counts = stageCounts([review(), review(), review({ self_submitted_at: T }), review({ self_submitted_at: T, manager_submitted_at: T })])
    expect(counts).toMatchObject({ total: 4, not_started: 2, awaiting_manager: 1, awaiting_calibration: 1, awaiting_publish: 0 })
    expect(stageCounts([]).total).toBe(0)
  })

  it("says HR is needed to calibrate or to publish, and at no other step", () => {
    expect(needsHr("awaiting_calibration")).toBe(true)
    expect(needsHr("awaiting_publish")).toBe(true)
    for (const other of ["not_started", "awaiting_manager", "published", "acknowledged"] as const) expect(needsHr(other)).toBe(false)
  })

  it("offers the same next action as the row buttons", () => {
    expect(nextAction(review())).toBeNull()
    expect(nextAction(review({ self_submitted_at: T }))).toBe("review")
    expect(nextAction(review({ self_submitted_at: T, manager_submitted_at: T }))).toBe("calibrate")
    expect(nextAction(review({ self_submitted_at: T, manager_submitted_at: T, hr_calibrated_at: T }))).toBe("publish")
    expect(nextAction(review({ self_submitted_at: T, manager_submitted_at: T, hr_calibrated_at: T, published_at: T }))).toBeNull()
  })

  it("rounds a share to a whole percent and copes with no total", () => {
    expect(percentOf(1, 3)).toBe(33)
    expect(percentOf(5, 0)).toBe(0)
    expect(percentOf(9, 3)).toBe(100)
  })
})

describe("filtering the queue", () => {
  const rows = [
    review({ employee_name: "Asha Verma", employee_code: "E1", manager_name: "Ravi Kumar" }),
    review({ employee_name: "Meena Iyer", employee_code: "E2", manager_name: "Sunil Rao", self_submitted_at: T, manager_submitted_at: T }),
    review({ employee_name: "Dev Shah", employee_code: "E3", manager_name: "Sunil Rao", self_submitted_at: T, manager_submitted_at: T, hr_calibrated_at: T }),
  ]

  it("searches name, code and manager without caring about case", () => {
    expect(filterReviews(rows, " MEENA ", "").map(item => item.employee_code)).toEqual(["E2"])
    expect(filterReviews(rows, "e3", "").map(item => item.employee_code)).toEqual(["E3"])
    expect(filterReviews(rows, "sunil", "").map(item => item.employee_code)).toEqual(["E2", "E3"])
  })

  it("narrows by step, with Needs HR meaning calibrate or publish", () => {
    expect(filterReviews(rows, "", "not_started").map(item => item.employee_code)).toEqual(["E1"])
    expect(filterReviews(rows, "", "needs_hr").map(item => item.employee_code)).toEqual(["E2", "E3"])
    expect(filterReviews(rows, "", "published")).toEqual([])
  })

  it("combines both and leaves the list it was given alone", () => {
    const before = [...rows]
    expect(filterReviews(rows, "sunil", "awaiting_publish").map(item => item.employee_code)).toEqual(["E3"])
    expect(rows).toEqual(before)
  })

  it("reports a filter as active only when something narrows the list", () => {
    expect(hasActiveFilters("", "")).toBe(false)
    expect(hasActiveFilters("  ", "")).toBe(false)
    expect(hasActiveFilters("a", "")).toBe(true)
    expect(hasActiveFilters("", "needs_hr")).toBe(true)
  })
})

describe("cycle dates", () => {
  it("reads a date and refuses anything else", () => {
    expect(parseDay("2026-11-05")?.getDate()).toBe(5)
    expect(parseDay("2026-11-05T10:00:00Z")?.getMonth()).toBe(10)
    for (const bad of ["", "soon", null, undefined, "05-11-2026"]) expect(parseDay(bad as never)).toBeNull()
  })

  it("counts whole days between two dates, ignoring the time of day", () => {
    expect(daysBetween(day("2026-11-01"), day("2026-11-11"))).toBe(10)
    expect(daysBetween(new Date(2026, 10, 1, 23, 59), new Date(2026, 10, 2, 0, 1))).toBe(1)
    expect(daysBetween(day("2026-11-11"), day("2026-11-01"))).toBe(-10)
  })

  it("places today and the due dates along a running cycle", () => {
    const progress = cycleProgress(cycle, day("2026-11-15"))
    expect(progress?.phase).toBe("running")
    expect(progress?.daysLeft).toBe(46)
    expect(Math.round(progress?.percent ?? 0)).toBe(Math.round((45 / 91) * 100))
    expect(progress?.milestones.map(item => [item.key, item.state])).toEqual([["start", "done"], ["self", "next"], ["manager", "later"], ["end", "later"]])
  })

  it("knows a cycle that has not started and one that has ended", () => {
    expect(cycleProgress(cycle, day("2026-09-20"))).toMatchObject({ phase: "upcoming", percent: 0 })
    expect(cycleProgress(cycle, day("2027-01-10"))).toMatchObject({ phase: "ended", daysLeft: 0, percent: 100 })
  })

  it("gives no timeline for dates that cannot make one", () => {
    expect(cycleProgress({ ...cycle, period_end: "2026-10-01" }, day("2026-11-01"))).toBeNull()
    expect(cycleProgress({ ...cycle, period_start: "" }, day("2026-11-01"))).toBeNull()
  })

  it("flags a self review as overdue only after the deadline and only if it is still missing", () => {
    expect(isSelfReviewOverdue(review(), cycle, day("2026-11-16"))).toBe(true)
    expect(isSelfReviewOverdue(review(), cycle, day("2026-11-15"))).toBe(false)
    expect(isSelfReviewOverdue(review({ self_submitted_at: T }), cycle, day("2026-11-30"))).toBe(false)
    expect(isSelfReviewOverdue(review(), null, day("2026-11-30"))).toBe(false)
  })

  it("phrases how close a date is", () => {
    const today = day("2026-11-10")
    expect(relativeDay("2026-11-10", today)).toBe("today")
    expect(relativeDay("2026-11-11", today)).toBe("tomorrow")
    expect(relativeDay("2026-11-09", today)).toBe("yesterday")
    expect(relativeDay("2026-11-15", today)).toBe("in 5 days")
    expect(relativeDay("2026-11-05", today)).toBe("5 days ago")
    expect(relativeDay("nope", today)).toBe("")
  })
})
