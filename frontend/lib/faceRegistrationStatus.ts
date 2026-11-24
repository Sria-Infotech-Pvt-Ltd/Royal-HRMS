// How an employee's Face ID registration reads on the HR page. Pure: no component state, safe to import anywhere.

import { tr } from "@/lib/i18n/tr"
import type { FaceRegistrationRequest, FaceRegistrationStatus, FaceRosterCounts, FaceRosterFilter } from "@/types/faceRegistration"

/** The three states a request can be in, plus "none" for an employee with no request at all. */
export type FaceState = FaceRegistrationStatus | "none"

export interface FaceStateMeta {
  label:    string
  badge:    string
  icon:     string
  tone:     "success" | "warn" | "error" | "neutral"
  headline: string
}

export const FACE_STATE_META: Record<FaceState, FaceStateMeta> = {
  approved: { label: "Approved",       badge: "badge-success", icon: "ti-shield-check", tone: "success", headline: "Face ID is registered" },
  pending:  { label: "Pending",        badge: "badge-warn",    icon: "ti-hourglass",    tone: "warn",    headline: "Waiting for approval" },
  rejected: { label: "Rejected",       badge: "badge-error",   icon: "ti-shield-x",     tone: "error",   headline: "Registration was rejected" },
  none:     { label: "Not registered", badge: "badge-neutral", icon: "ti-face-id-error", tone: "neutral", headline: "No Face ID yet" },
}

export function faceStateOf(status: FaceState | undefined | null): FaceState {
  return status && status in FACE_STATE_META ? status : "none"
}

/** Replacing an approved Face ID needs a confirmation first; every other state goes straight to capture. */
export function needsReplaceConfirmation(state: FaceState): boolean {
  return state === "approved"
}

export function actionLabel(state: FaceState): string {
  return state === "approved" ? "Update Face ID" : "Register Face ID"
}

type Detail = Pick<FaceRegistrationRequest, "approved_at" | "approved_by_name" | "created_at" | "notes">

/** The plain-words detail lines under the headline, given a date formatter. Empty when there is nothing more to say. */
export function stateDetails(state: FaceState, request: Partial<Detail> | null | undefined, formatDate: (iso: string) => string): string[] {
  if (!request) return []
  const lines: string[] = []
  if (state === "approved" && request.approved_at) {
    lines.push(request.approved_by_name
      ? tr("Registered on {date} by {name}.", { date: formatDate(request.approved_at), name: request.approved_by_name })
      : tr("Registered on {date}.", { date: formatDate(request.approved_at) }))
  }
  if (state === "pending" && request.created_at) lines.push(tr("Submitted on {date}. It can be approved from the Approvals page.", { date: formatDate(request.created_at) }))
  if (state === "rejected") {
    if (request.approved_at) lines.push(request.approved_by_name
      ? tr("Reviewed on {date} by {name}.", { date: formatDate(request.approved_at), name: request.approved_by_name })
      : tr("Reviewed on {date}.", { date: formatDate(request.approved_at) }))
    if (request.notes?.trim()) lines.push(tr("Reason: {reason}", { reason: request.notes.trim() }))
  }
  return lines
}

/** "Showing 1–20 of 53 employees", or null when there are none. */
export function pickerRange(page: number, pageSize: number, shown: number, total: number): string | null {
  if (total <= 0 || shown <= 0) return null
  const first = (page - 1) * pageSize + 1
  return tr("Showing {from}–{to} of {total}", { from: first, to: first + shown - 1, total })
}

export function personInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "?"
  return ((parts[0][0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] ?? "" : "")).toUpperCase()
}

export const EMPTY_ROSTER_COUNTS: FaceRosterCounts = { total: 0, approved: 0, pending: 0, rejected: 0, none: 0, incomplete: 0 }

/** Counts from the server, with anything missing or not a number treated as zero. */
export function readRosterCounts(raw: Partial<FaceRosterCounts> | undefined): FaceRosterCounts {
  const read = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : 0)
  return {
    total: read(raw?.total), approved: read(raw?.approved), pending: read(raw?.pending),
    rejected: read(raw?.rejected), none: read(raw?.none), incomplete: read(raw?.incomplete),
  }
}

/** Whole-number share of employees who have a usable Face ID; 0 when there are no employees. */
export function coveragePercent(counts: Pick<FaceRosterCounts, "total" | "approved">): number {
  if (counts.total <= 0) return 0
  return Math.min(100, Math.floor((counts.approved / counts.total) * 100))
}

export interface CoverageItem { filter: FaceRosterFilter; label: string; value: number; tone: "success" | "warn" | "error" | "neutral" }

/** The parts of the coverage bar and the filters under it, in the order they are drawn. */
export function coverageItems(counts: FaceRosterCounts): CoverageItem[] {
  return [
    { filter: "approved", label: "Registered",     value: counts.approved, tone: "success" },
    { filter: "pending",  label: "Pending",        value: counts.pending,  tone: "warn" },
    { filter: "rejected", label: "Rejected",       value: counts.rejected, tone: "error" },
    { filter: "none",     label: "Not registered", value: counts.none,     tone: "neutral" },
  ]
}

/** The width of one part of the bar as a percentage of all employees. */
export function segmentWidth(value: number, total: number): number {
  return total > 0 ? Math.min(100, (value / total) * 100) : 0
}

/** What to tell the person when the list is empty, given the filter that is on. */
export function emptyListMessage(filter: FaceRosterFilter, hasSearch: boolean): { title: string; text: string } {
  if (hasSearch) return { title: "No employees match", text: "Try a different name, email or ID, or clear the filter." }
  if (filter === "incomplete") return { title: "Everyone is registered", text: "No employee is waiting on a Face ID." }
  if (filter) return { title: "Nobody in this group", text: "No employees have this Face ID status right now." }
  return { title: "No employees", text: "Active employees will appear here." }
}
