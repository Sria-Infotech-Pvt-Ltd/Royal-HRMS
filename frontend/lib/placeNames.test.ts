import { describe, expect, it } from "vitest"
import { canonicalName } from "./placeNames"

describe("canonicalName", () => {
  const states = ["Goa", "Karnataka", "Tamil Nadu"]
  it("finds the listed spelling ignoring case and spaces", () => {
    expect(canonicalName(states, "KARNATAKA")).toBe("Karnataka")
    expect(canonicalName(states, " goa ")).toBe("Goa")
    expect(canonicalName(states, "tamil   nadu")).toBe("Tamil Nadu")
  })
  it("returns null for unknown or empty names", () => {
    expect(canonicalName(states, "Narnia")).toBeNull()
    expect(canonicalName(states, "")).toBeNull()
    expect(canonicalName([], "Goa")).toBeNull()
  })
})
