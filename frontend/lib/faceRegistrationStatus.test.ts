import { describe, expect, it } from "vitest"
import { FACE_STATE_META, actionLabel, faceStateOf, needsReplaceConfirmation, personInitials, pickerRange, stateDetails } from "./faceRegistrationStatus"

const fmt = (iso: string) => `D(${iso})`

describe("face registration helpers", () => {
  it("maps a status, or the lack of one, to a state", () => {
    expect(faceStateOf("approved")).toBe("approved")
    expect(faceStateOf("pending")).toBe("pending")
    expect(faceStateOf("rejected")).toBe("rejected")
    expect(faceStateOf(undefined)).toBe("none")
    expect(faceStateOf(null)).toBe("none")
    expect(faceStateOf("weird" as never)).toBe("none")
  })

  it("has a label, badge, icon and headline for every state", () => {
    for (const meta of Object.values(FACE_STATE_META)) {
      expect(meta.label && meta.badge && meta.icon && meta.headline).toBeTruthy()
    }
  })

  it("asks for confirmation only before replacing an approved Face ID", () => {
    expect(needsReplaceConfirmation("approved")).toBe(true)
    for (const state of ["pending", "rejected", "none"] as const) expect(needsReplaceConfirmation(state)).toBe(false)
  })

  it("words the action as update for an approved Face ID and register otherwise", () => {
    expect(actionLabel("approved")).toBe("Update Face ID")
    for (const state of ["pending", "rejected", "none"] as const) expect(actionLabel(state)).toBe("Register Face ID")
  })

  it("says when and by whom an approved Face ID was registered", () => {
    expect(stateDetails("approved", { approved_at: "2026-11-01", approved_by_name: "Asha" }, fmt)).toEqual(["Registered on D(2026-11-01) by Asha."])
    expect(stateDetails("approved", { approved_at: "2026-11-01", approved_by_name: "" }, fmt)).toEqual(["Registered on D(2026-11-01)."])
  })

  it("says a pending request can be approved from the Approvals page", () => {
    expect(stateDetails("pending", { created_at: "2026-11-02" }, fmt)[0]).toContain("Approvals page")
  })

  it("shows the reason a request was rejected, and skips a blank one", () => {
    const lines = stateDetails("rejected", { approved_at: "2026-11-03", approved_by_name: "Ravi", notes: " Blurry photo " }, fmt)
    expect(lines).toEqual(["Reviewed on D(2026-11-03) by Ravi.", "Reason: Blurry photo"])
    expect(stateDetails("rejected", { notes: "   " }, fmt)).toEqual([])
  })

  it("has no detail lines when there is no request", () => {
    expect(stateDetails("none", undefined, fmt)).toEqual([])
    expect(stateDetails("none", {}, fmt)).toEqual([])
  })

  it("describes which employees the page is showing", () => {
    expect(pickerRange(1, 20, 20, 53)).toBe("Showing 1–20 of 53")
    expect(pickerRange(3, 20, 13, 53)).toBe("Showing 41–53 of 53")
    expect(pickerRange(1, 20, 0, 0)).toBeNull()
  })

  it("makes initials from first and last name, and copes with one name or none", () => {
    expect(personInitials("G.Durga prasad")).toBe("GP")
    expect(personInitials("Asha Verma")).toBe("AV")
    expect(personInitials("Madonna")).toBe("M")
    expect(personInitials("  ")).toBe("?")
  })
})
