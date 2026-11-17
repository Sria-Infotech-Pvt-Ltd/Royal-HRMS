import { describe, expect, it } from "vitest"
import { shortHoursText } from "./shortHours"

describe("shortHoursText", () => {
  it("returns the text the server sent when there is a shortfall", () => {
    expect(shortHoursText({ short_minutes: 80, short_display: "1h 20m" })).toBe("1h 20m")
  })

  it("falls back to minutes if the text is missing", () => {
    expect(shortHoursText({ short_minutes: 40 })).toBe("40m")
  })

  it("returns null when nothing is short or the record is missing", () => {
    expect(shortHoursText({ short_minutes: 0, short_display: null })).toBeNull()
    expect(shortHoursText({})).toBeNull()
    expect(shortHoursText(undefined)).toBeNull()
    expect(shortHoursText(null)).toBeNull()
  })
})
