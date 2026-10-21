import { describe, expect, it } from "vitest"
import { describeBulkImportOutcome } from "./bulkImportStatus"

describe("describeBulkImportOutcome", () => {
  it("says nothing was created and retry is safe when the server never received it", () => {
    const text = describeBulkImportOutcome({ state: "not_received" })
    expect(text).toContain("no employees were created")
    expect(text).toContain("safe to upload")
  })

  it("reports exact counts for a completed import and warns against re-uploading", () => {
    const text = describeBulkImportOutcome({ state: "completed", total_rows: 50, created: 48, skipped: 1, failed: 1 })
    expect(text).toContain("48 created, 1 skipped, 1 failed out of 50 rows")
    expect(text).toContain("Do not upload the same file again")
  })

  it("reports partial creation for an interrupted import", () => {
    const text = describeBulkImportOutcome({ state: "interrupted", total_rows: 50, created_since_start: 31 })
    expect(text).toContain("31 of 50")
  })

  it("asks the user to wait while the import is still running", () => {
    expect(describeBulkImportOutcome({ state: "in_progress", created_since_start: 12 })).toContain("still running")
  })

  it("falls back to a safe message when the status check itself failed", () => {
    expect(describeBulkImportOutcome(null)).toContain("could not be checked")
  })
})
