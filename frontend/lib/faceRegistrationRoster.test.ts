import { describe, expect, it } from "vitest"
import { coverageItems, coveragePercent, emptyListMessage, readRosterCounts, segmentWidth, faceStateOf } from "./faceRegistrationStatus"

const counts = { total: 50, approved: 37, pending: 4, rejected: 2, none: 7, incomplete: 13 }

describe("face ID roster helpers", () => {
  it("reads the server's counts and treats anything missing or not a number as zero", () => {
    expect(readRosterCounts(counts)).toEqual(counts)
    expect(readRosterCounts(undefined)).toEqual({ total: 0, approved: 0, pending: 0, rejected: 0, none: 0, incomplete: 0 })
    expect(readRosterCounts({ total: "9" as unknown as number, approved: NaN, pending: 2 })).toMatchObject({ total: 0, approved: 0, pending: 2 })
  })

  it("works out the share of employees with a usable Face ID, rounding down so 100% means everyone", () => {
    expect(coveragePercent(counts)).toBe(74)
    expect(coveragePercent({ total: 3, approved: 2 })).toBe(66)
    expect(coveragePercent({ total: 3, approved: 3 })).toBe(100)
    expect(coveragePercent({ total: 0, approved: 0 })).toBe(0)
    expect(coveragePercent({ total: 200, approved: 199 })).toBe(99)
  })

  it("lists registered, pending, rejected and not registered in that order, each with its own filter", () => {
    expect(coverageItems(readRosterCounts(counts)).map(item => [item.filter, item.value])).toEqual([["approved", 37], ["pending", 4], ["rejected", 2], ["none", 7]])
  })

  it("sizes each part of the bar against everyone and never past the whole", () => {
    expect(segmentWidth(25, 50)).toBe(50)
    expect(segmentWidth(0, 50)).toBe(0)
    expect(segmentWidth(5, 0)).toBe(0)
    expect(segmentWidth(80, 50)).toBe(100)
  })

  it("makes the four parts add up to the whole bar", () => {
    const items = coverageItems(readRosterCounts(counts))
    expect(items.reduce((sum, item) => sum + segmentWidth(item.value, counts.total), 0)).toBeCloseTo(100)
  })

  it("explains an empty list by what is filtered", () => {
    expect(emptyListMessage("incomplete", false).title).toBe("Everyone is registered")
    expect(emptyListMessage("pending", false).title).toBe("Nobody in this group")
    expect(emptyListMessage("", false).title).toBe("No employees")
    expect(emptyListMessage("incomplete", true).title).toBe("No employees match")
  })

  it("reads an employee's state, with a missing one meaning not registered", () => {
    expect(faceStateOf("none")).toBe("none")
    expect(faceStateOf("approved")).toBe("approved")
    expect(faceStateOf(undefined)).toBe("none")
  })
})
