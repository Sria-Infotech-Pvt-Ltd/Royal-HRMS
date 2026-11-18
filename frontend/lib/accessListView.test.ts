import { describe, expect, it } from "vitest"
import { accessShare, hueOf, initialsOf } from "./accessListView"

describe("initialsOf", () => {
  it("takes the first and last name", () => {
    expect(initialsOf("Gadde Durga Prasad")).toBe("GP")
    expect(initialsOf("aarav nair")).toBe("AN")
    expect(initialsOf("Sria")).toBe("S")
    expect(initialsOf("   ")).toBe("?")
  })
})

describe("hueOf", () => {
  it("is steady for a name and stays on the colour wheel", () => {
    expect(hueOf("Aarav Nair")).toBe(hueOf("Aarav Nair"))
    expect(hueOf("Aarav Nair")).toBeGreaterThanOrEqual(0)
    expect(hueOf("Aarav Nair")).toBeLessThan(360)
  })
})

describe("accessShare", () => {
  it("splits a person's permissions into whole percentages that add up to 100", () => {
    const share = accessShare({ from_baseline: 7, from_seat: 4, extra: 2 })
    expect(share.everyone + share.position + share.extra).toBe(100)
    expect(share.everyone).toBeGreaterThan(share.position)
  })
  it("is all zero for nobody", () => {
    expect(accessShare({ from_baseline: 0, from_seat: 0, extra: 0 })).toEqual({ everyone: 0, position: 0, extra: 0 })
  })
})
