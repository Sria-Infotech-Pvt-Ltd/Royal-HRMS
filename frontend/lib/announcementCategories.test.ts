import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"
import { CAT_BADGE, CAT_LABEL, CATEGORIES, FILTERS, categoryLabel } from "./announcementCategories"

describe("announcement categories", () => {
  it("lists the seven types with the labels people read", () => {
    expect(CATEGORIES.map(option => [option.value, option.label])).toEqual([
      ["general", "Company News"], ["policy", "Policy"], ["event", "Events"], ["celebration", "Celebration"],
      ["holiday", "Holiday & Closures"], ["payroll", "Payroll & Benefits"], ["urgent", "Urgent"],
    ])
  })

  it("gives every type a label, a badge colour and a pill, and no value twice", () => {
    const values = CATEGORIES.map(option => option.value)
    expect(new Set(values).size).toBe(values.length)
    for (const option of CATEGORIES) {
      expect(CAT_LABEL[option.value]).toBe(option.label)
      expect(CAT_BADGE[option.value]).toMatch(/^badge-/)
    }
    expect(FILTERS.map(filter => filter.value)).toEqual(["", ...values])
    expect(FILTERS[0].label).toBe("All Posts")
  })

  it("shows Urgent in red so it stands out, and gives each colour to a sensible type", () => {
    expect(CAT_BADGE.urgent).toBe("badge-error")
    expect(CAT_BADGE.payroll).toBe("badge-teal")
  })

  it("turns a word from the server into its label, and shows an unknown word as it is rather than hiding it", () => {
    expect(categoryLabel("event")).toBe("Events")
    expect(categoryLabel("holiday")).toBe("Holiday & Closures")
    expect(categoryLabel("something-new")).toBe("something-new")
  })

  it("matches the server's list exactly, so the two can never drift apart", () => {
    const source = readFileSync(path.resolve(__dirname, "../../backend/apps/announcements/models.py"), "utf8")
    const constants = new Map([...source.matchAll(/^\s*(CATEGORY_[A-Z]+)\s*=\s*'([a-z]+)'/gm)].map(match => [match[1], match[2]]))
    const serverChoices = [...source.matchAll(/^\s*\((CATEGORY_[A-Z]+),\s*'([^']+)'\)/gm)].map(match => [constants.get(match[1]), match[2]])
    expect(serverChoices.length).toBeGreaterThan(0)
    expect(CATEGORIES.map(option => [option.value, option.label])).toEqual(serverChoices)
  })
})
