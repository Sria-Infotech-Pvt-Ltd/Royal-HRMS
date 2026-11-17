import { describe, expect, it } from "vitest"
import { isWorkFromHome } from "./workMode"

describe("isWorkFromHome", () => {
  it("is true only for work mode wfh", () => {
    expect(isWorkFromHome({ work_mode: "wfh" })).toBe(true)
    expect(isWorkFromHome({ work_mode: "office" })).toBe(false)
    expect(isWorkFromHome({ work_mode: null })).toBe(false)
    expect(isWorkFromHome({})).toBe(false)
    expect(isWorkFromHome(undefined)).toBe(false)
    expect(isWorkFromHome(null)).toBe(false)
  })
})
