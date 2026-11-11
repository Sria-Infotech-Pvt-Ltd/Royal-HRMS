import { describe, expect, it } from "vitest"
import {
  POLL_ACTIVE_MS, POLL_WAITING_FOR_EMAILS_MS, canCancelJob, canRetryEmails, describeCommitResult, describeEmails, describeJob, emailsInFlight, hasRowErrors,
  pollDelayMs, validateImportFile,
} from "./employeeImport"
import type { ImportCommitResult, ImportInviteProgress, ImportJobProgress } from "@/types/employeeImport"

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

const job = (over: Partial<ImportJobProgress> = {}, invites: Partial<ImportJobProgress["invitations"]> = {}): ImportJobProgress => ({
  job_id: "j1", status: "completed", is_active: false, file_name: "staff.xlsx", total_rows: 13, processed_rows: 13, created: 13, failed_rows: 0, percent: 100,
  cancel_requested: false, failure_code: "", created_at: null, started_at: null, finished_at: null,
  invitations: { held: false, total: 13, pending: 0, processing: 0, sent: 13, skipped: 0, failed: 0, ...invites }, invitation_failures: [], ...over,
})

describe("describeJob (employee creation only)", () => {
  it("says the import is queued and survives closing the window", () => expect(describeJob(job({ status: "queued", is_active: true }))).toMatch(/close this window/))
  it("shows row progress while running", () =>
    expect(describeJob(job({ status: "running", is_active: true, processed_rows: 4, created: 3, failed_rows: 1 }))).toBe("Creating employees: 4 of 13 rows processed, 3 created, 1 row failed."))
  it("says it is stopping after a cancel request", () => expect(describeJob(job({ status: "running", is_active: true, cancel_requested: true, created: 2 }))).toMatch(/Stopping after the current batch. 2 employees/))
  it("reports completion, singular and plural", () => {
    expect(describeJob(job({ created: 1 }))).toBe("1 employee created.")
    expect(describeJob(job())).toBe("13 employees created.")
  })
  it("points to the error report when rows failed", () => expect(describeJob(job({ status: "completed_with_errors", created: 11, failed_rows: 2 }))).toMatch(/11 employees created. 2 rows could not be imported: download the error report/))
  it("keeps created employees when cancelled", () => expect(describeJob(job({ status: "cancelled", created: 6 }))).toMatch(/6 employees had already been created and stay/))
  it("explains a stopped import in plain words", () => {
    expect(describeJob(job({ status: "failed", failure_code: "batch_failed", created: 3 }))).toMatch(/could not be saved after several attempts. 3 employees/)
    expect(describeJob(job({ status: "failed", failure_code: "something_new" }))).toMatch(/unexpected problem/)
  })
})

describe("describeEmails (delivery is a separate statement)", () => {
  it("counts sent, waiting and failed", () => expect(describeEmails(job({}, { sent: 10, pending: 1, processing: 1, failed: 1 }))).toBe("Activation emails: 10 sent, 2 waiting, 1 failed. The employees exist; retry the failed emails below."))
  it("says nothing was needed when there are no invitations", () => expect(describeEmails(job({}, { total: 0, sent: 0 }))).toBe("No activation emails were needed."))
  it("says emails are queued while employees are still being created", () => expect(describeEmails(job({ is_active: true, status: "running" }, { total: 0, sent: 0 }))).toMatch(/queued after each employee/))
  it("explains a hold by an administrator", () => expect(describeEmails(job({}, { held: true, sent: 0, pending: 13 }))).toMatch(/switched off by an administrator/))
  it("mentions invitations that were not needed", () => expect(describeEmails(job({}, { sent: 12, skipped: 1 }))).toMatch(/1 not needed/))
})

describe("polling and button rules", () => {
  it("polls quickly while the job runs", () => expect(pollDelayMs(job({ is_active: true, status: "running" }))).toBe(POLL_ACTIVE_MS))
  it("polls slowly while only emails remain", () => expect(pollDelayMs(job({}, { pending: 2, sent: 11 }))).toBe(POLL_WAITING_FOR_EMAILS_MS))
  it("stops polling when everything has settled", () => expect(pollDelayMs(job())).toBeNull())
  it("does not poll forever while an administrator holds the emails", () => expect(pollDelayMs(job({}, { held: true, pending: 13, sent: 0 }))).toBeNull())
  it("counts emails in flight", () => expect(emailsInFlight(job({}, { pending: 2, processing: 1 }))).toBe(3))
  it("offers cancel only to a running job that is not already stopping", () => {
    expect(canCancelJob(job({ is_active: true, status: "running" }))).toBe(true)
    expect(canCancelJob(job({ is_active: true, status: "running", cancel_requested: true }))).toBe(false)
    expect(canCancelJob(job())).toBe(false)
  })
  it("offers retry only when emails failed, and the error report only when rows failed", () => {
    expect(canRetryEmails(job({}, { failed: 1 }))).toBe(true)
    expect(canRetryEmails(job())).toBe(false)
    expect(hasRowErrors(job({ failed_rows: 2 }))).toBe(true)
    expect(hasRowErrors(job())).toBe(false)
  })
})
