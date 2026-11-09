import { describe, expect, it } from "vitest"
import { describeCommitResult, validateImportFile } from "./employeeImport"
import type { ImportCommitResult, ImportInviteProgress } from "@/types/employeeImport"

const result = (over: Partial<ImportCommitResult>): ImportCommitResult => ({
  batch_id: "b", created: 3, already_committed: false, invites_total: 3, invites_sent: 0, invite_failures: [], ...over,
})

describe("validateImportFile", () => {
  it("accepts a normal xlsx", () => expect(validateImportFile({ name: "Staff.XLSX", size: 1000 })).toBeNull())
  it("rejects csv and other types", () => {
    expect(validateImportFile({ name: "a.csv", size: 10 })).toMatch(/xlsx/)
    expect(validateImportFile({ name: "a.xls", size: 10 })).toMatch(/xlsx/)
  })
  it("rejects empty and oversize", () => {
    expect(validateImportFile({ name: "a.xlsx", size: 0 })).toMatch(/empty/)
    expect(validateImportFile({ name: "a.xlsx", size: 5 * 1024 * 1024 + 1 })).toMatch(/too large/)
  })
})

describe("describeCommitResult", () => {
  const progress = (over: Partial<ImportInviteProgress>): ImportInviteProgress => ({ batch_id: "b", state: "done", total: 3, sent: 3, failed: [], ...over })
  it("says emails are being sent before any progress is known", () => expect(describeCommitResult(result({}))).toBe("3 employees created. Activation emails are being sent."))
  it("shows progress while sending", () => expect(describeCommitResult(result({}), progress({ state: "sending", sent: 1 }))).toBe("3 employees created. Sending activation emails: 1 of 3 done."))
  it("reports success with invitations", () => expect(describeCommitResult(result({}), progress({}))).toBe("3 employees created. Activation emails were sent to all of them."))
  it("separates invitation failures from creation", () => {
    const text = describeCommitResult(result({ created: 1 }), progress({ total: 1, sent: 0, failed: [{ row: 2, employee_id: "1", reason: "x" }] }))
    expect(text).toMatch(/1 employee created/)
    expect(text).toMatch(/1 activation email could not be sent/)
  })
  it("explains a retried batch", () => expect(describeCommitResult(result({ already_committed: true }))).toMatch(/already completed/))
})
