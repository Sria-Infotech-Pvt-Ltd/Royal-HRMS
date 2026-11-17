import { describe, expect, it } from "vitest"
import { readCounts } from "@/hooks/useOnboardingQueue"
import { buildApprovalCards, isApprovedStatus, rangeLabel, statusMeta } from "./_filters"

describe("onboarding approvals helpers", () => {
  it("builds four cards that filter by the matching status, with a line of context each", () => {
    const cards = buildApprovalCards({ total: 39, submitted: 7, rejected: 2, approved: 30 })
    expect(cards.map(card => [card.key, card.value])).toEqual([["", 39], ["submitted", 7], ["rejected", 2], ["approved", 30]])
    expect(cards[1].sub).toBe("Waiting for your review")
    expect(cards[3].sub).toBe("Completed, now on the employee list")
  })

  it("says so plainly when nothing is there", () => {
    const cards = buildApprovalCards({ total: 0, submitted: 0, rejected: 0, approved: 0 })
    expect(cards.map(card => card.sub)).toEqual(["No submissions yet", "Nothing waiting for you", "Nobody sent back", "None approved yet"])
  })

  it("labels known statuses and shows an unknown one as a neutral Pending", () => {
    expect(statusMeta("submitted").label).toBe("Awaiting review")
    expect(statusMeta("rejected").label).toBe("Needs revision")
    expect(statusMeta("complete")).toMatchObject({ label: "Approved", badge: "badge-success" }) // how the server stores an approved person
    expect(statusMeta("something-new")).toMatchObject({ label: "Pending", badge: "badge-neutral" })
  })

  it("treats the server's stored word and the filter word for an approved person as the same thing", () => {
    expect(isApprovedStatus("complete")).toBe(true)
    expect(isApprovedStatus("approved")).toBe(true)
    expect(isApprovedStatus("submitted")).toBe(false)
  })

  it("describes the rows on the page against the whole list", () => {
    expect(rangeLabel(1, 20, 20, 53)).toBe("Showing 1–20 of 53")
    expect(rangeLabel(3, 20, 13, 53)).toBe("Showing 41–53 of 53")
    expect(rangeLabel(1, 20, 0, 0)).toBeNull()
  })

  it("reads the server's totals and treats anything missing or not a number as zero", () => {
    expect(readCounts({ total: 5, submitted: 3, rejected: 1, approved: 1 })).toEqual({ total: 5, submitted: 3, rejected: 1, approved: 1 })
    expect(readCounts(undefined)).toEqual({ total: 0, submitted: 0, rejected: 0, approved: 0 })
    expect(readCounts({ total: "5" as unknown as number, submitted: NaN, rejected: 1 })).toEqual({ total: 0, submitted: 0, rejected: 1, approved: 0 })
  })
})
