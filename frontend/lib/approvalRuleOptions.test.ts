import { describe, expect, it } from "vitest"
import { buildApproverOptions, fromSelectValue, toSelectValue } from "./approvalRuleOptions"
import type { ApprovalRulePerson } from "@/types/approvalMatrix"

const kabir: ApprovalRulePerson = { id: "u1", employee_id: "EMP00001", full_name: "Kabir Rao", department: "Application Development" }
const meera: ApprovalRulePerson = { id: "u2", employee_id: "EMP00005", full_name: "Meera Kulkarni", department: "" }

describe("buildApproverOptions", () => {
  it("offers the two relationships first, then every eligible person", () => {
    const options = buildApproverOptions([kabir, meera])
    expect(options.map(option => option.value)).toEqual(["reporting_manager", "hr", "person:u1", "person:u2"])
    expect(options[2].label).toBe("Kabir Rao (EMP00001) — Application Development")
    expect(options[3].label).toBe("Meera Kulkarni (EMP00005)")
  })

  it("still offers the two relationships when nobody is eligible", () => {
    expect(buildApproverOptions([]).map(option => option.value)).toEqual(["reporting_manager", "hr"])
  })

  it("keeps a saved person in the list even if they are no longer eligible", () => {
    const options = buildApproverOptions([kabir], { userId: "gone", label: "Old Approver" })
    expect(options[2]).toEqual({ value: "person:gone", label: "Old Approver (no longer eligible)" })
  })

  it("does not duplicate a saved person who is still eligible", () => {
    expect(buildApproverOptions([kabir], { userId: "u1", label: "Kabir Rao" })).toHaveLength(3)
  })
})

describe("select values", () => {
  it("turns a saved choice into a dropdown value", () => {
    expect(toSelectValue("reporting_manager", null)).toBe("reporting_manager")
    expect(toSelectValue("hr", null)).toBe("hr")
    expect(toSelectValue("person", "u1")).toBe("person:u1")
    expect(toSelectValue("person", null)).toBe("")
    expect(toSelectValue("", null)).toBe("")
  })

  it("turns a dropdown value back into what the server expects", () => {
    expect(fromSelectValue("person:u1")).toEqual({ kind: "person", userId: "u1" })
    expect(fromSelectValue("hr")).toEqual({ kind: "hr", userId: null })
    expect(fromSelectValue("reporting_manager")).toEqual({ kind: "reporting_manager", userId: null })
    expect(fromSelectValue("")).toEqual({ kind: "", userId: null })
    expect(fromSelectValue("anything-else")).toEqual({ kind: "", userId: null })
  })

  it("round-trips every kind", () => {
    for (const [kind, userId] of [["reporting_manager", null], ["hr", null], ["person", "u9"]] as const) {
      expect(fromSelectValue(toSelectValue(kind, userId))).toEqual({ kind, userId })
    }
  })
})
