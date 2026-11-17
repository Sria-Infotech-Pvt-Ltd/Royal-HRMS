// Shapes the HR Performance hub reads from /performance/cycles/ and /performance/reviews/hr-queue/.

export interface ApiCycle {
  id: string
  name: string
  period_start: string
  period_end: string
  self_review_due: string
  manager_review_due: string
  status: "draft" | "active" | "closed"
}

export interface ApiReview {
  id: string
  employee_name: string
  employee_code: string
  cycle_name: string
  metric_reference: string
  what_changed: string
  key_strengths: string
  development_areas: string
  support_needed: string
  next_cycle_goal: string
  self_rating: string
  self_submitted_at: string | null
  manager_name: string
  manager_rating: string
  manager_notes: string
  manager_submitted_at: string | null
  hr_calibrated_at: string | null
  published_at: string | null
  acknowledged_at: string | null
  status: "not_started" | "self_review" | "hr_calibration" | "published" | "completed"
  status_display: string
}

export interface HrQueueData {
  cycle: ApiCycle | null
  reviews: ApiReview[]
  stats: {
    total_employees_with_reviews: number
    self_reviews_done: number
    manager_reviews_done: number
    goals_at_risk: number
  } | null
}
