/** "1h 20m" when a finished day stayed Present / Late but fell short of the full-day minimum ("hours not completed"), else null. */
export function shortHoursText(record: { short_minutes?: number; short_display?: string | null } | null | undefined): string | null {
  if (!record || !record.short_minutes || record.short_minutes <= 0) return null
  return record.short_display ?? `${record.short_minutes}m`
}
