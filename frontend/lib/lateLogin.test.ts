import { describe, expect, it } from "vitest"
import { isLateLogin, lateLoginText } from "./lateLogin"

describe("late login", () => {
  it("is only a day that was late but counted as Present", () => {
    expect(isLateLogin({ late_forgiven: true })).toBe(true)
    expect(isLateLogin({ late_forgiven: false })).toBe(false)
    expect(isLateLogin({})).toBe(false)
    expect(isLateLogin(null)).toBe(false)
    expect(isLateLogin(undefined)).toBe(false)
  })

  it("explains it with the punch-in time and the grace time when known", () => {
    expect(lateLoginText({ late_forgiven: true, clockIn: "10:14", late_after: "09:15" }))
      .toBe("Punched in 10:14 (after 09:15). Full hours were completed, so the day counts as Present.")
    expect(lateLoginText({ late_forgiven: true })).toBe("Punched in. Full hours were completed, so the day counts as Present.")
  })

  it("has no text for an ordinary day", () => {
    expect(lateLoginText({ late_forgiven: false, clockIn: "10:14" })).toBeNull()
    expect(lateLoginText(null)).toBeNull()
  })
})
