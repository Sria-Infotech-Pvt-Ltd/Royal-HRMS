import { describe, expect, it } from "vitest"
import { filterQueryParams, isFutureDate, isStageFilter, lifecycleNote, ONBOARDING_LABEL, STAGE_LABEL } from "./employeeLifecycle"

describe("labels", () => {
  it("uses the agreed wording", () => {
    expect(STAGE_LABEL.unknown).toBe("Unknown (Date Missing)")
    expect(ONBOARDING_LABEL).toEqual({
      not_started: "Not Started", in_progress: "In Progress", awaiting_review: "Awaiting Review",
      needs_revision: "Needs Revision", completed: "Completed",
    })
  })
})

describe("filterQueryParams", () => {
  it("passes ordinary statuses through as `status`", () => expect(filterQueryParams("onboarding")).toEqual({ status: "onboarding" }))
  it("sends nothing for all", () => expect(filterQueryParams("all")).toEqual({}))
  it("maps stage values to employment_stage", () => {
    expect(filterQueryParams("stage:pre_joining")).toEqual({ employment_stage: "pre_joining" })
    expect(filterQueryParams("stage:unknown")).toEqual({ employment_stage: "unknown" })
  })
  it("leaves stage filters out of the stats request", () => expect(filterQueryParams("stage:terminated", true)).toEqual({}))
  it("recognises stage filter values", () => {
    expect(isStageFilter("stage:terminated")).toBe(true)
    expect(isStageFilter("active")).toBe(false)
  })
})

describe("lifecycleNote", () => {
  it("shows the joining date for Pre-Joining", () => expect(lifecycleNote("pre_joining", "2026-11-09")).toEqual({ text: "Joins 09/11/2026", tone: "info" }))
  it("flags a missing joining date for HR", () => expect(lifecycleNote("unknown", "")).toMatchObject({ tone: "warn" }))
  it("flags termination", () => expect(lifecycleNote("terminated", "2020-01-01")?.tone).toBe("crit"))
  it("says nothing extra for Active, unless the account is locked", () => {
    expect(lifecycleNote("active", "2020-01-01")).toBeNull()
    expect(lifecycleNote(undefined, "2020-01-01")).toBeNull()
    expect(lifecycleNote("active", "2020-01-01", true)).toEqual({ text: "Account locked", tone: "warn" })
  })
})

describe("isFutureDate", () => {
  const now = new Date(2026, 10, 6, 9, 0) // 6 Nov 2026, local time
  it("is true only after today", () => {
    expect(isFutureDate("2026-11-07", now)).toBe(true)
    expect(isFutureDate("2026-11-06", now)).toBe(false)
    expect(isFutureDate("2026-11-05", now)).toBe(false)
  })
  it("is false for a blank date", () => {
    expect(isFutureDate("", now)).toBe(false)
    expect(isFutureDate(null, now)).toBe(false)
  })
})
