/** True when a calendar day was worked from home (an approved work-from-home request covered it). */
export function isWorkFromHome(record: { work_mode?: string | null } | null | undefined): boolean {
  return record?.work_mode === "wfh"
}
