import { describe, expect, it } from "vitest"
import { changesByModule } from "./PermissionChangeReview"

const item = (codename: string) => ({ codename, action: codename.split(".")[1], description: "", is_sensitive: false })

describe("changesByModule", () => {
  const modules: [string, ReturnType<typeof item>[]][] = [
    ["leave", [item("leave.view"), item("leave.view_own")]],
    ["payroll", [item("payroll.view")]],
  ]
  it("lists what saving would switch on and off, and leaves untouched modules out", () => {
    const saved = new Set(["leave.view", "payroll.view"])
    const granted = new Set(["leave.view_own", "payroll.view"])
    expect(changesByModule(modules, granted, saved)).toEqual([{ module: "leave", added: ["view own"], removed: ["view"] }])
  })
  it("is empty when nothing changed", () => {
    expect(changesByModule(modules, new Set(["leave.view"]), new Set(["leave.view"]))).toEqual([])
  })
})
