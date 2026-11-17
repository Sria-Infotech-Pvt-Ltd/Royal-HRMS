/** The statuses the onboarding approvals list shows: waiting for review, sent back for changes, and approved. */
export type QueueStatus = "submitted" | "rejected" | "approved"
export type QueueStatusFilter = "" | QueueStatus

/** Totals for the whole list the signed-in person may see, whatever page or filter is showing. */
export interface QueueCounts {
  total:     number
  submitted: number
  rejected:  number
  approved:  number
}

/** One page of the queue as the server sends it. */
export interface QueuePage<Row> {
  results:     Row[]
  count:       number
  page:        number
  page_size?:  number
  total_pages: number
  counts?:     Partial<QueueCounts>
}
