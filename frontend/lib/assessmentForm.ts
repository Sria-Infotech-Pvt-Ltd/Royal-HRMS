// Pure helpers for the New / Edit Assessment form: no component state, safe to import anywhere.
//
// The form keeps its numbers as text, the way the saved record is read back:
//   max_attempts    ""  = use the global setting   "0" = unlimited   "N" = N attempts
//   time_limit_mins ""  = use the global setting                     "N" = N minutes

import type { AssessmentForm } from "@/app/dashboard/assessments/_types"

export type AttemptsMode = "global" | "unlimited" | "limited"
export type TimeMode = "global" | "limited"

/** Used only to pre-fill the box when someone switches to a custom time limit and no global limit exists to start from. */
export const FALLBACK_TIME_LIMIT_MINS = 30

export function attemptsMode(value: string): AttemptsMode {
  if (value.trim() === "") return "global"
  return value.trim() === "0" ? "unlimited" : "limited"
}

export function timeMode(value: string): TimeMode {
  return value.trim() === "" ? "global" : "limited"
}

/** The text to store when switching mode, keeping a number the person already typed. */
export function attemptsForMode(mode: AttemptsMode, current: string): string {
  if (mode === "global") return ""
  if (mode === "unlimited") return "0"
  return /^[1-9]\d*$/.test(current.trim()) ? current.trim() : "1"
}

export function timeForMode(mode: TimeMode, current: string, globalMinutes: number | null | undefined): string {
  if (mode === "global") return ""
  if (/^[1-9]\d*$/.test(current.trim())) return current.trim()
  return String(globalMinutes && globalMinutes > 0 ? globalMinutes : FALLBACK_TIME_LIMIT_MINS)
}

export interface FormErrors { title?: string; pass?: string; attempts?: string; time?: string }

const isWholeNumber = (value: string) => /^\d+$/.test(value.trim())

export function validateAssessmentForm(form: Pick<AssessmentForm, "title" | "pass_percentage" | "max_attempts" | "time_limit_mins">): FormErrors {
  const errors: FormErrors = {}
  if (!form.title.trim()) errors.title = "Give the assessment a title."
  const pass = Number(form.pass_percentage)
  if (!isWholeNumber(form.pass_percentage) || pass < 1 || pass > 100) errors.pass = "Enter a pass mark between 1 and 100."
  if (form.max_attempts.trim() !== "" && !isWholeNumber(form.max_attempts)) errors.attempts = "Attempts must be a whole number."
  if (attemptsMode(form.max_attempts) === "limited" && Number(form.max_attempts) < 1) errors.attempts = "Allow at least 1 attempt."
  if (form.time_limit_mins.trim() !== "" && (!isWholeNumber(form.time_limit_mins) || Number(form.time_limit_mins) < 1)) {
    errors.time = "Enter the time limit in whole minutes, at least 1."
  }
  return errors
}

export const hasErrors = (errors: FormErrors) => Object.keys(errors).length > 0

export interface GlobalDefaults { maxAttempts: number | null | undefined; timeLimitMins: number | null | undefined }

/** "Unlimited attempts", "3 attempts", ... for the global default shown next to the "use global" choice. */
export function describeAttempts(count: number | null | undefined): string {
  if (count == null) return "not set"
  if (count === 0) return "unlimited attempts"
  return `${count} attempt${count !== 1 ? "s" : ""}`
}

export function describeTime(minutes: number | null | undefined): string {
  return minutes && minutes > 0 ? `${minutes} min` : "no time limit"
}

/** One line of what the form currently says, e.g. "70% to pass · 3 attempts (global) · 30 min". */
export function rulesSummary(form: Pick<AssessmentForm, "pass_percentage" | "max_attempts" | "time_limit_mins">, defaults: GlobalDefaults): string[] {
  const attempts = attemptsMode(form.max_attempts)
  const time = timeMode(form.time_limit_mins)
  return [
    `${form.pass_percentage || "—"}% to pass`,
    attempts === "global" ? `${describeAttempts(defaults.maxAttempts)} (global)` : attempts === "unlimited" ? "Unlimited attempts" : describeAttempts(Number(form.max_attempts)),
    time === "global" ? `${describeTime(defaults.timeLimitMins)} (global)` : `${form.time_limit_mins} min`,
  ]
}

/** What is sent to the server. Blank attempts / time mean "inherit the global setting" (null). */
export function buildAssessmentPayload(form: AssessmentForm) {
  return {
    title:           form.title.trim(),
    description:     form.description,
    is_active:       form.is_active,
    is_default:      false, // assessments are never auto-assigned; HR assigns them explicitly
    pass_percentage: Number(form.pass_percentage),
    max_attempts:    form.max_attempts.trim() !== "" ? Number(form.max_attempts) : null,
    time_limit_mins: form.time_limit_mins.trim() !== "" ? Number(form.time_limit_mins) : null,
  }
}
