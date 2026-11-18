import { describe, expect, it } from "vitest"
import { columnItems, coverageOf, filterCounts, quickSetChanges, sensitiveOn, stateOf, visibleModules, type MatrixModule } from "./permissionMatrixView"

const item = (codename: string, is_sensitive = false) => ({ codename, action: codename.split(".")[1], description: "", is_sensitive })
const modules: MatrixModule[] = [
  ["leave", [item("leave.view"), item("leave.create"), item("leave.approve")]],
  ["payroll", [item("payroll.view"), item("payroll.export", true)]],
  ["asset", [item("asset.view")]],
]

describe("coverage and state", () => {
  it("counts what is on and names the state", () => {
    const granted = new Set(["leave.view", "leave.create"])
    expect(coverageOf(modules[0][1], granted)).toEqual({ on: 2, total: 3 })
    expect(stateOf({ on: 2, total: 3 })).toBe("some")
    expect(stateOf({ on: 3, total: 3 })).toBe("all")
    expect(stateOf({ on: 0, total: 3 })).toBe("none")
    expect(stateOf({ on: 0, total: 0 })).toBe("none")
  })
})

describe("visibleModules", () => {
  const granted = new Set(["leave.view", "leave.create", "leave.approve", "payroll.view"])
  const names = (list: MatrixModule[]) => list.map(([name]) => name)

  it("shows everything with no search and the All filter", () => {
    expect(names(visibleModules(modules, granted, "", "all"))).toEqual(["leave", "payroll", "asset"])
  })
  it("filters by how much of a module is on", () => {
    expect(names(visibleModules(modules, granted, "", "on"))).toEqual(["leave"])
    expect(names(visibleModules(modules, granted, "", "partial"))).toEqual(["payroll"])
    expect(names(visibleModules(modules, granted, "", "off"))).toEqual(["asset"])
    expect(names(visibleModules(modules, granted, "", "sensitive"))).toEqual(["payroll"])
  })
  it("a module-name search keeps every permission of the module, a permission search keeps only the matches", () => {
    expect(visibleModules(modules, granted, "pay", "all")[0][1]).toHaveLength(2)
    const byAction = visibleModules(modules, granted, "approve", "all")
    expect(names(byAction)).toEqual(["leave"])
    expect(byAction[0][1].map(entry => entry.codename)).toEqual(["leave.approve"])
  })
  it("returns nothing when nothing matches", () => {
    expect(visibleModules(modules, granted, "zzz", "all")).toEqual([])
  })
})

describe("filterCounts, columnItems and sensitiveOn", () => {
  const granted = new Set(["leave.view", "leave.create", "leave.approve", "payroll.export"])
  it("counts modules per filter", () => {
    expect(filterCounts(modules, granted)).toEqual({ all: 3, on: 1, partial: 1, off: 1, sensitive: 1 })
  })
  it("collects one action across the modules", () => {
    expect(columnItems(modules, "view").map(entry => entry.codename)).toEqual(["leave.view", "payroll.view", "asset.view"])
  })
  it("counts sensitive permissions that are switched on", () => {
    expect(sensitiveOn(modules, granted)).toBe(1)
    expect(sensitiveOn(modules, new Set())).toBe(0)
  })
})

describe("quickSetChanges", () => {
  const unlocked = () => false
  it("View only keeps reading on and switches everything else off", () => {
    const granted = new Set(["leave.create", "payroll.export"])
    const { add, remove } = quickSetChanges(modules, granted, "view_only", unlocked)
    expect(add.sort()).toEqual(["asset.view", "leave.view", "payroll.view"])
    expect(remove.sort()).toEqual(["leave.create", "payroll.export"])
  })
  it("Everything adds only what is missing, Nothing removes only what is on", () => {
    const granted = new Set(["leave.view"])
    expect(quickSetChanges(modules, granted, "everything", unlocked).add).toHaveLength(5)
    expect(quickSetChanges(modules, granted, "everything", unlocked).remove).toEqual([])
    expect(quickSetChanges(modules, granted, "nothing", unlocked)).toEqual({ add: [], remove: ["leave.view"] })
  })
  it("never touches a locked permission", () => {
    const isLocked = (codename: string) => codename === "payroll.export" || codename === "leave.view"
    const granted = new Set(["leave.view"])
    expect(quickSetChanges(modules, granted, "nothing", isLocked).remove).toEqual([])
    expect(quickSetChanges(modules, granted, "everything", isLocked).add).not.toContain("payroll.export")
  })
})
