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
