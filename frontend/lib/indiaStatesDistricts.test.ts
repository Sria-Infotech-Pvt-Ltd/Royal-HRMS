import { describe, expect, it } from "vitest"
import { INDIA_STATES, INDIA_STATE_NAMES, canonicalName, districtsForState } from "./indiaStatesDistricts"

const collator = new Intl.Collator("en", { sensitivity: "base" })
const isAToZ = (items: string[]) => items.every((item, index) => index === 0 || collator.compare(items[index - 1], item) <= 0)

describe("India states and districts", () => {
  it("lists all 28 states and 8 union territories, each once", () => {
    expect(INDIA_STATE_NAMES).toHaveLength(36)
    expect(new Set(INDIA_STATE_NAMES).size).toBe(36)
  })

  it("lists states A to Z, whatever order the data is written in", () => {
    expect(isAToZ(INDIA_STATE_NAMES)).toBe(true)
    expect(INDIA_STATE_NAMES[0]).toBe("Andaman and Nicobar Islands")
    expect(INDIA_STATE_NAMES.indexOf("Telangana")).toBeGreaterThan(INDIA_STATE_NAMES.indexOf("Tamil Nadu"))
  })

  it("lists every state's districts A to Z", () => {
    for (const state of INDIA_STATES) expect(isAToZ(districtsForState(state.name)), state.name).toBe(true)
  })

  it("keeps every district, with none dropped or repeated by the sorting", () => {
    for (const state of INDIA_STATES) {
      const listed = districtsForState(state.name)
      expect(listed.length, state.name).toBe(state.districts.length)
      expect(new Set(listed).size, state.name).toBe(listed.length)
    }
  })

  it("has no state without a district", () => {
    for (const state of INDIA_STATES) expect(state.districts.length, state.name).toBeGreaterThan(0)
  })

  it("includes the districts created in recent years", () => {
    expect(districtsForState("Madhya Pradesh")).toEqual(expect.arrayContaining(["Maihar", "Mauganj", "Pandhurna"]))
    expect(districtsForState("Assam")).toEqual(expect.arrayContaining(["Bajali", "Tamulpur"]))
    expect(districtsForState("Telangana")).toEqual(expect.arrayContaining(["Hanumakonda", "Mulugu", "Narayanpet"]))
  })

  it("finds a state's districts however it was typed or looked up: capitals, extra spaces", () => {
    expect(districtsForState("TELANGANA")).toEqual(districtsForState("Telangana"))
    expect(districtsForState("  tamil   nadu ")).toEqual(districtsForState("Tamil Nadu"))
    expect(districtsForState("Atlantis")).toEqual([])
    expect(districtsForState("")).toEqual([])
  })

  it("gives the listed spelling of a name, or null when it is not listed", () => {
    expect(canonicalName(INDIA_STATE_NAMES, "KARNATAKA")).toBe("Karnataka")
    expect(canonicalName(INDIA_STATE_NAMES, " goa ")).toBe("Goa")
    expect(canonicalName(INDIA_STATE_NAMES, "Narnia")).toBeNull()
    expect(canonicalName(INDIA_STATE_NAMES, "")).toBeNull()
  })
})

describe("closestName: the PIN data spells some districts differently", () => {
  const telangana = districtsForState("Telangana")

  it("finds the listed spelling of a district written another way", async () => {
    const { closestName } = await import("./indiaStatesDistricts")
    expect(closestName(telangana, "Jangoan")).toBe("Jangaon")
    expect(closestName(telangana, "Jagitial")).toBe("Jagtial")
    expect(closestName(telangana, "KUMURAM BHEEM ASIFABAD")).toBe("Komaram Bheem Asifabad")
    expect(closestName(telangana, "MEDCHAL MALKAJGIRI")).toBe("Medchal–Malkajgiri")
    expect(closestName(telangana, "HYDERABAD")).toBe("Hyderabad")
  })

  it("does not force an unrelated name into a match", async () => {
    const { closestName } = await import("./indiaStatesDistricts")
    expect(closestName(telangana, "Narnia")).toBeNull()
    expect(closestName(telangana, "")).toBeNull()
    expect(closestName([], "Hyderabad")).toBeNull()
  })
})
