// "Late login": a person punched in after the grace time but still worked the full hours, so the company's rule counts the day as Present.
// The day's status therefore no longer says they were late; this tag does, for the employee and for managers. Display only: the stored
// status (and what payroll reads from it) does not change.

export const LATE_LOGIN_LABEL = "Late login"
export const LATE_LOGIN_MEANING = "Punched in after the grace time, but the full hours were worked, so the day counts as Present."

interface LateLoginRecord {
  late_forgiven?: boolean
  late_after?: string | null
  clockIn?: string | null
}

export function isLateLogin(record: LateLoginRecord | null | undefined): boolean {
  return Boolean(record?.late_forgiven)
}

/** "Punched in 10:14 (after 09:15). Full hours were completed, so the day counts as Present."; null when the day was not a late login. */
export function lateLoginText(record: LateLoginRecord | null | undefined): string | null {
  if (!record || !isLateLogin(record)) return null
  const at = record.clockIn ? ` ${record.clockIn}` : ""
  const after = record.late_after ? ` (after ${record.late_after})` : ""
  return `Punched in${at}${after}. Full hours were completed, so the day counts as Present.`
}
