import { describe, expect, it } from "vitest"
import { MODULE_ROUTES, notificationRoute } from "./notificationRoutes"

describe("notificationRoute", () => {
  it("opens the employee a joining notice is about", () => {
    expect(notificationRoute({ module: "system", reference_id: "employee:10000009" })).toBe("/dashboard/employees/10000009")
  })
  it("opens your own profile for the welcome notice", () => {
    expect(notificationRoute({ module: "system", reference_id: "profile" })).toBe("/dashboard/profile")
  })
  it("escapes the employee id", () => {
    expect(notificationRoute({ module: "system", reference_id: "employee:A/B" })).toBe("/dashboard/employees/A%2FB")
  })
  it("sends other system notices, and malformed references, to the dashboard", () => {
    expect(notificationRoute({ module: "system", reference_id: "" })).toBe("/dashboard")
    expect(notificationRoute({ module: "system", reference_id: "employee:" })).toBe("/dashboard")
    expect(notificationRoute({ module: "system", reference_id: "whatever" })).toBe("/dashboard")
  })
  it("keeps every other module on its fixed page, ignoring the reference", () => {
    expect(notificationRoute({ module: "leave", reference_id: "employee:1" })).toBe("/dashboard/leave")
    expect(notificationRoute({ module: "payroll", reference_id: "" })).toBe(MODULE_ROUTES.payroll)
  })
  it("opens the announcement a notification is about in the employee workspace", () => {
    expect(notificationRoute({ module: "announcement", reference_id: "12" })).toBe("/dashboard/ess?tab=announcements&announcement=12")
  })
  it("opens the Announcements tab when the reference is not an announcement id", () => {
    expect(notificationRoute({ module: "announcement", reference_id: "x" })).toBe("/dashboard/ess?tab=announcements")
    expect(notificationRoute({ module: "announcement", reference_id: "" })).toBe("/dashboard/ess?tab=announcements")
  })
  it("falls back for a module the app does not know", () => {
    expect(notificationRoute({ module: "brand_new" as never, reference_id: "" })).toBe("/dashboard")
  })
})
