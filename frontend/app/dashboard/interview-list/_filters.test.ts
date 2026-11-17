import { describe, expect, it } from "vitest"
import { buildStatCards, fmtTime, hasActiveFilters, interviewSummary, needsDetails, shareOfTotal } from "./_filters"
import type { RecruitmentStats } from "./_data"

const stats: RecruitmentStats = { total: 10, pending: 4, selected: 3, rejected: 1, pending_review: 0 }

describe("interview list helpers", () => {
  it("shows a share only when there is something to take a share of", () => {
    expect(shareOfTotal(4, 10)).toBe("40% of all candidates")
    expect(shareOfTotal(0, 0)).toBeNull()
  })

  it("builds the four cards, in order, each with a line of context", () => {
    const cards = buildStatCards(stats)
    expect(cards.map(card => [card.key, card.value])).toEqual([["", 10], ["pending", 4], ["selected", 3], ["rejected", 1]])
    expect(cards[1].sub).toBe("40% of all candidates")
    expect(cards[0].sub).toBe("Across all company codes")
    expect(buildStatCards(stats, "Hyderabad")[0].sub).toBe("In Hyderabad")
  })

  it("says how many are waiting for HR review on the Selected card", () => {
    expect(buildStatCards({ ...stats, pending_review: 2 })[2].sub).toBe("2 awaiting HR review")
  })

  it("shows dashes and Loading until the numbers arrive, and a plain note when there are no candidates", () => {
    expect(buildStatCards(null).map(card => card.value)).toEqual([null, null, null, null])
    expect(buildStatCards(null)[1].sub).toBe("Loading…")
    expect(buildStatCards({ total: 0, pending: 0, selected: 0, rejected: 0, pending_review: 0 })[1].sub).toBe("No candidates yet")
  })

  it("counts a filter as active only when the person can actually change it", () => {
    expect(hasActiveFilters("", "", "", true)).toBe(false)
    expect(hasActiveFilters("  ", "", "", true)).toBe(false)
    expect(hasActiveFilters("asha", "", "", false)).toBe(true)
    expect(hasActiveFilters("", "pending", "", false)).toBe(true)
    expect(hasActiveFilters("", "", 3, true)).toBe(true)
    expect(hasActiveFilters("", "", 3, false)).toBe(false)
  })

  it("trims the seconds from a time", () => {
    expect(fmtTime("10:30:00")).toBe("10:30")
    expect(fmtTime(null)).toBeNull()
  })

  it("describes an unscheduled interview without a date", () => {
    const summary = interviewSummary({ interview_date: null, interview_time: null, interview_mode: "video_call", interviewer_name: "" })
    expect(summary.when).toBeNull()
    expect(summary.interviewer).toBeNull()
  })

  it("asks for details only on a referred candidate that is missing a branch or a date", () => {
    expect(needsDetails({ referral_by: 5, branch: null, interview_date: "2026-11-20" })).toBe(true)
    expect(needsDetails({ referral_by: 5, branch: 1, interview_date: null })).toBe(true)
    expect(needsDetails({ referral_by: 5, branch: 1, interview_date: "2026-11-20" })).toBe(false)
    expect(needsDetails({ referral_by: null, branch: null, interview_date: null })).toBe(false)
  })
})
