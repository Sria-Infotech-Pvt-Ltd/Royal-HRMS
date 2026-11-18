import { describe, expect, it } from "vitest"
import type { PermissionTemplate } from "@/components/settings/permissionTemplateTypes"
import { copyName, filterCounts, modulesOfTemplate, sensitiveCount, summarise, totalPermissions, visibleTemplates } from "./permissionTemplatesView"

const item = (codename: string, is_sensitive = false) => ({ codename, action: codename.split(".")[1], description: "", is_sensitive })
const catalogue = {
  leave: [item("leave.view"), item("leave.approve")],
  payroll: [item("payroll.view"), item("payroll.export", true), item("payroll.edit")],
}
const template = (over: Partial<PermissionTemplate>): PermissionTemplate => ({
  id: "t", name: "T", description: "", can_manage_team: false, can_manage_branch: false, permission_codenames: [], position_count: 0,
  created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z", ...over,
})
const manager = template({ id: "1", name: "Manager", description: "Runs a team", can_manage_team: true, permission_codenames: ["leave.view", "leave.approve", "payroll.export"], position_count: 3, updated_at: "2026-11-10T00:00:00Z" })
const hr = template({ id: "2", name: "HR", can_manage_branch: true, permission_codenames: ["payroll.view", "payroll.edit"], position_count: 1, updated_at: "2026-11-12T00:00:00Z" })
const blank = template({ id: "3", name: "Blank" })
const all = [manager, hr, blank]

describe("what a template contains", () => {
  it("groups by module, biggest first, and ignores codenames the catalogue no longer has", () => {
    const shares = modulesOfTemplate({ ...manager, permission_codenames: [...manager.permission_codenames, "gone.view"] }, catalogue)
    expect(shares).toEqual([{ module: "leave", actions: ["view", "approve"] }, { module: "payroll", actions: ["export"] }])
  })
  it("counts sensitive permissions and the catalogue total", () => {
    expect(sensitiveCount(manager, catalogue)).toBe(1)
    expect(sensitiveCount(hr, catalogue)).toBe(0)
    expect(totalPermissions(catalogue)).toBe(5)
  })
})

describe("search, filter, sort", () => {
  const names = (list: PermissionTemplate[]) => list.map(entry => entry.name)
  it("searches name and description", () => {
    expect(names(visibleTemplates(all, "team", "all", "name"))).toEqual(["Manager"])
    expect(names(visibleTemplates(all, "hr", "all", "name"))).toEqual(["HR"])
  })
  it("filters by scope, emptiness and use", () => {
    expect(names(visibleTemplates(all, "", "team", "name"))).toEqual(["Manager"])
    expect(names(visibleTemplates(all, "", "branch", "name"))).toEqual(["HR"])
    expect(names(visibleTemplates(all, "", "empty", "name"))).toEqual(["Blank"])
    expect(names(visibleTemplates(all, "", "unused", "name"))).toEqual(["Blank"])
    expect(filterCounts(all)).toEqual({ all: 3, team: 1, branch: 1, empty: 1, unused: 1 })
  })
  it("sorts by name, permissions, positions and recency", () => {
    expect(names(visibleTemplates(all, "", "all", "name"))).toEqual(["Blank", "HR", "Manager"])
    expect(names(visibleTemplates(all, "", "all", "permissions"))).toEqual(["Manager", "HR", "Blank"])
    expect(names(visibleTemplates(all, "", "all", "positions"))).toEqual(["Manager", "HR", "Blank"])
    expect(names(visibleTemplates(all, "", "all", "updated"))).toEqual(["HR", "Manager", "Blank"])
  })
})

describe("summary and copy names", () => {
  it("adds the numbers above the cards", () => {
    expect(summarise(all, catalogue)).toEqual({ templates: 3, applications: 4, empty: 1, sensitive: 1 })
  })
  it("never reuses an existing name for a copy", () => {
    expect(copyName("Manager", ["Manager"])).toBe("Manager (copy)")
    expect(copyName("Manager", ["Manager", "manager (copy)"])).toBe("Manager (copy 2)")
  })
})
