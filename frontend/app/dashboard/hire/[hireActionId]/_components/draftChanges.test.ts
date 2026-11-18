import { describe, expect, it } from "vitest"
import { changedDraftFields } from "./draftChanges"

describe("changedDraftFields", () => {
  it("sends only what differs from the server's draft", () => {
    const known = { first_name: "Asha", last_name: "Rao", date_of_birth: "1995-08-15" }
    expect(changedDraftFields({ first_name: "Asha", last_name: "Rao", date_of_birth: "1996-01-01" }, known)).toEqual({ date_of_birth: "1996-01-01" })
  })
  it("never sends empty boxes the server does not have, so a stale copy cannot blank real values", () => {
    expect(changedDraftFields({ first_name: "", date_of_birth: "", gender: "" }, { first_name: "Asha" })).toEqual({ first_name: "" })
    expect(changedDraftFields({ first_name: "", gender: "" }, {})).toEqual({})
  })
  it("sends a cleared field so a person can still empty a box", () => {
    expect(changedDraftFields({ middle_name: "" }, { middle_name: "K" })).toEqual({ middle_name: "" })
  })
  it("treats a missing value and an empty one as the same", () => {
    expect(changedDraftFields({ blood_group: "" }, {})).toEqual({})
  })
  it("always sends settings and re-sends a filled email and mobile for the duplicate warning", () => {
    expect(changedDraftFields({ employment_type: "Permanent", email: "a@b.com", phone: "9876543210", pan_number: "X" }, { email: "a@b.com", phone: "9876543210", pan_number: "X" }))
      .toEqual({ employment_type: "Permanent", email: "a@b.com", phone: "9876543210" })
  })
  it("compares lists by content", () => {
    expect(changedDraftFields({ family_entries: [{ id: "1", name: "A" }] }, { family_entries: [{ id: "1", name: "A" }] })).toEqual({})
    expect(changedDraftFields({ family_entries: [{ id: "1", name: "B" }] }, { family_entries: [{ id: "1", name: "A" }] })).toEqual({ family_entries: [{ id: "1", name: "B" }] })
  })
})
