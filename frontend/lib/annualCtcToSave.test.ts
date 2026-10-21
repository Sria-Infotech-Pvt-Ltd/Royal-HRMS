import { describe, expect, it } from "vitest"
import { annualCtcToSave, buildPay } from "./payBreakup"

// Mirrors the Basic pay dialog: the breakup is built from round(CTC / 12).
const monthlyCtcFor = (annual: number) => buildPay(Math.round(annual / 12)).monthlyCtc

describe("annualCtcToSave", () => {
  it.each([400000, 750000, 2800000, 400001, 399999, 1000000, 123457, 600005])(
    "keeps the entered annual CTC %i exactly when there are no overrides", annual => {
      expect(annualCtcToSave(annual, monthlyCtcFor(annual), false)).toBe(annual)
    },
  )

  it("reproduces the UAT bug without the fix: 400000 re-summed from monthly is 399996", () => {
    expect(monthlyCtcFor(400000) * 12).toBe(399996)
  })

  it("uses the re-summed breakup when earnings are overridden", () => {
    expect(annualCtcToSave(400000, 40000, true)).toBe(480000)
  })
})
