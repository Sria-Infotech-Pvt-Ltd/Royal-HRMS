function toValidDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function pad(value: number): string {
  return String(value).padStart(2, "0")
}

export function formatDate(value: string | Date | null | undefined): string {
  const date = toValidDate(value)
  if (!date) return ""
  return `${pad(date.getDate())}-${pad(date.getMonth() + 1)}-${date.getFullYear()}`
}

export function formatDateTime(value: string | Date | null | undefined): string {
  const date = toValidDate(value)
  if (!date) return ""
  return `${formatDate(date)}, ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** dd/mm/yyyy — the Employee Directory reference's date style (the rest of the app keeps dd-mm-yyyy). */
export function formatDateSlash(value: string | Date | null | undefined): string {
  const date = toValidDate(value)
  if (!date) return ""
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`
}

/** HH:mm, 24-hour. */
export function formatTimeHm(value: string | Date | null | undefined): string {
  const date = toValidDate(value)
  if (!date) return ""
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

/** "Apr 2026 – Mar 2027" for a financial year that starts on `fyStart`. */
export function financialYearRangeLabel(fyStart: Date): string {
  const end = new Date(fyStart.getFullYear() + 1, fyStart.getMonth() - 1, 1)
  return `${MONTH_SHORT[fyStart.getMonth()]} ${fyStart.getFullYear()} – ${MONTH_SHORT[end.getMonth()]} ${end.getFullYear()}`
}
