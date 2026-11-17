import { describe, expect, it } from "vitest"
import type { AssessmentForm } from "@/app/dashboard/assessments/_types"
import {
  attemptsForMode, attemptsMode, buildAssessmentPayload, describeAttempts, describeTime, hasErrors, rulesSummary,
  timeForMode, timeMode, validateAssessmentForm, FALLBACK_TIME_LIMIT_MINS,
} from "./assessmentForm"

const form = (over: Partial<AssessmentForm> = {}): AssessmentForm => ({
  title: "Onboarding", description: "", is_active: true, is_default: false, pass_percentage: "70", max_attempts: "", time_limit_mins: "", ...over,
})

describe("assessment form helpers", () => {
  it("reads attempts: blank is the global setting, 0 is unlimited, a number is a limit", () => {
    expect(attemptsMode("")).toBe("global")
    expect(attemptsMode("0")).toBe("unlimited")
    expect(attemptsMode("3")).toBe("limited")
  })

  it("keeps a number the person already typed when switching modes, and starts a limit at 1 otherwise", () => {
    expect(attemptsForMode("global", "3")).toBe("")
    expect(attemptsForMode("unlimited", "3")).toBe("0")
    expect(attemptsForMode("limited", "3")).toBe("3")
    expect(attemptsForMode("limited", "")).toBe("1")
    expect(attemptsForMode("limited", "0")).toBe("1")
  })

  it("starts a custom time limit from the global one when there is one", () => {
    expect(timeMode("")).toBe("global")
    expect(timeMode("20")).toBe("limited")
    expect(timeForMode("global", "20", 45)).toBe("")
    expect(timeForMode("limited", "20", 45)).toBe("20")
    expect(timeForMode("limited", "", 45)).toBe("45")
    expect(timeForMode("limited", "", null)).toBe(String(FALLBACK_TIME_LIMIT_MINS))
  })

  it("accepts a normal form", () => {
    expect(hasErrors(validateAssessmentForm(form()))).toBe(false)
    expect(hasErrors(validateAssessmentForm(form({ max_attempts: "0", time_limit_mins: "30" })))).toBe(false)
  })

  it("asks for a title", () => {
    expect(validateAssessmentForm(form({ title: "   " })).title).toBeTruthy()
  })

  it("keeps the pass mark between 1 and 100 and a whole number", () => {
    for (const bad of ["0", "101", "", "abc", "70.5", "-5"]) expect(validateAssessmentForm(form({ pass_percentage: bad })).pass, bad).toBeTruthy()
    for (const good of ["1", "70", "100"]) expect(validateAssessmentForm(form({ pass_percentage: good })).pass, good).toBeUndefined()
  })

  it("refuses odd attempts and time limits", () => {
    expect(validateAssessmentForm(form({ max_attempts: "abc" })).attempts).toBeTruthy()
    expect(validateAssessmentForm(form({ max_attempts: "-1" })).attempts).toBeTruthy()
    expect(validateAssessmentForm(form({ time_limit_mins: "0" })).time).toBeTruthy()
    expect(validateAssessmentForm(form({ time_limit_mins: "1.5" })).time).toBeTruthy()
  })

  it("describes the global defaults in plain words", () => {
    expect(describeAttempts(0)).toBe("unlimited attempts")
    expect(describeAttempts(1)).toBe("1 attempt")
    expect(describeAttempts(3)).toBe("3 attempts")
    expect(describeAttempts(undefined)).toBe("not set")
    expect(describeTime(null)).toBe("no time limit")
    expect(describeTime(30)).toBe("30 min")
  })

  it("summarises the rules and marks the ones taken from the global setting", () => {
    const defaults = { maxAttempts: 3, timeLimitMins: 30 }
    expect(rulesSummary(form(), defaults)).toEqual(["70% to pass", "3 attempts (global)", "30 min (global)"])
    expect(rulesSummary(form({ max_attempts: "0", time_limit_mins: "15" }), defaults)).toEqual(["70% to pass", "Unlimited attempts", "15 min"])
    expect(rulesSummary(form({ max_attempts: "2" }), defaults)[1]).toBe("2 attempts")
  })

  it("builds the payload the server expects: blank means inherit, and assessments are never auto-assigned", () => {
    expect(buildAssessmentPayload(form({ title: "  Safety  ", is_default: true }))).toEqual({
      title: "Safety", description: "", is_active: true, is_default: false, pass_percentage: 70, max_attempts: null, time_limit_mins: null,
    })
    expect(buildAssessmentPayload(form({ max_attempts: "0", time_limit_mins: "20" }))).toMatchObject({ max_attempts: 0, time_limit_mins: 20 })
  })
})
