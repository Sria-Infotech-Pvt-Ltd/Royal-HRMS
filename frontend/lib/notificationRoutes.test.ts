import { describe, expect, it } from "vitest"
import { MODULE_ROUTES, notificationRoute } from "./notificationRoutes"

describe("notificationRoute", () => {
  it("opens the employee a joining notice is about", () => {
    expect(notificationRoute({ module: "system", reference_id: "employee:10000009" })).toBe("/dashboard/employees/10000009")
  })
  it("opens the dashboard for your own welcome notice", () => {
    expect(notificationRoute({ module: "system", reference_id: "profile" })).toBe("/dashboard")
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
  it("opens the Employment tab, not My Profile, for confirmation and promotion notices", () => {
    expect(notificationRoute({ module: "confirmation", reference_id: "abc" })).toBe("/dashboard/ess?tab=employment")
    expect(notificationRoute({ module: "promotion", reference_id: "abc" })).toBe("/dashboard/ess?tab=employment")
  })
  it("opens the HR Help queue for a new HR Help ticket notice", () => {
    expect(notificationRoute({ module: "system", reference_id: "hr-help" })).toBe("/dashboard/approvals?section=hr_requests")
  })
  it("falls back for a module the app does not know", () => {
    expect(notificationRoute({ module: "brand_new" as never, reference_id: "" })).toBe("/dashboard")
  })
})

describe("notificationRoute: timesheet notices", () => {
  const SHEET = "2026-11-09:7b0f5c3e-1111-4222-8333-444455556666"
  it("takes an approver to Approvals > Timesheets when a timesheet is submitted for them", () => {
    expect(notificationRoute({ module: "timesheet", notification_type: "timesheet_submitted", reference_id: SHEET })).toBe("/dashboard/approvals?section=timesheets")
  })
  it("takes an approver to Approvals > Timesheets from the Monday reminder", () => {
    expect(notificationRoute({ module: "timesheet", notification_type: "timesheet_reminder", reference_id: "approver-day:2026-11-16" })).toBe("/dashboard/approvals?section=timesheets")
  })
  it("opens that week's timesheet in My Workspace when your own sheet is approved or sent back", () => {
    for (const type of ["timesheet_approved", "timesheet_returned"]) {
      expect(notificationRoute({ module: "timesheet", notification_type: type, reference_id: SHEET })).toBe("/dashboard/ess?tab=timesheet&week=2026-11-09")
    }
  })
  it("opens that week from the Friday reminder", () => {
    expect(notificationRoute({ module: "timesheet", notification_type: "timesheet_reminder", reference_id: "employee-week:2026-11-09" })).toBe("/dashboard/ess?tab=timesheet&week=2026-11-09")
  })
  it("still opens the timesheet view (this week) when the reference has no week, and never the bare dashboard", () => {
    expect(notificationRoute({ module: "timesheet", notification_type: "timesheet_approved", reference_id: "" })).toBe(MODULE_ROUTES.timesheet)
    expect(notificationRoute({ module: "timesheet", reference_id: "garbage" })).toBe("/dashboard/ess?tab=timesheet")
  })
  it("treats an older notice without a type as the employee's own sheet", () => {
    expect(notificationRoute({ module: "timesheet", reference_id: SHEET })).toBe("/dashboard/ess?tab=timesheet&week=2026-11-09")
  })
})
