import { describe, expect, it } from "vitest"
import { issueFor, validateHireStep, type HireSnapshot } from "./hireValidation"

const NOW = new Date("2026-11-18T10:00:00Z")
const base: HireSnapshot = {
  firstName: "Asha", middleName: "", lastName: "Verma", dateOfBirth: "1995-03-30", gender: "female", nationality: "Indian",
  email: "asha@example.com", phone: "+91 9876543210", alternateMobile: "",
  employment: { employment_type: "Full-time", branch: "Hyderabad", work_email: "", annual_ctc: "" },
  statutory: {
    pan_number: "ABCDE1234F", aadhaar_number: "123456789012", account_holder_name: "Asha Verma", account_number: "123456789",
    ifsc_code: "HDFC0001234", uan_number: "", passport_issue_date: "", passport_expiry: "",
  },
  familyEntries: [], nomineeEntries: [], educationEntries: [{ institution: "JNTU" }],
  documentTypes: ["pan_card", "aadhaar_card", "tenth_certificate", "twelfth_certificate", "degree_certificate"],
  requiredDocuments: [
    { key: "pan_card", label: "PAN Card" }, { key: "aadhaar_card", label: "Aadhaar Card" }, { key: "tenth_certificate", label: "10th Certificate" },
    { key: "twelfth_certificate", label: "12th Certificate" }, { key: "degree_certificate", label: "Degree Certificate" },
  ],
  phoneDigits: phone => phone.replace(/\D/g, "").replace(/^91/, "").length,
  isPlausiblePhone: phone => /[6-9]/.test(phone.replace(/\D/g, "").replace(/^91/, "")[0] ?? ""),
  now: NOW,
}
const withPatch = (patch: Partial<HireSnapshot>): HireSnapshot => ({ ...base, ...patch })
const fields = (step: number, patch: Partial<HireSnapshot> = {}) => validateHireStep(step, withPatch(patch)).map(issue => issue.field)

describe("a complete hire", () => {
  it("has no problems on any step", () => {
    for (let step = 0; step < 9; step++) expect(validateHireStep(step, base), `step ${step + 1}`).toEqual([])
  })
})

describe("every problem is reported at once, not one at a time", () => {
  it("lists all the missing identity fields together", () => {
    const issues = validateHireStep(0, withPatch({ firstName: "", lastName: "", dateOfBirth: "", gender: "", email: "", phone: "" }))
    expect(issues.map(issue => issue.field)).toEqual(["first_name", "last_name", "date_of_birth", "gender", "email", "phone"])
  })

  it("lists all the missing statutory fields together", () => {
    const empty = { pan_number: "", aadhaar_number: "", account_holder_name: "", account_number: "", ifsc_code: "", uan_number: "", passport_issue_date: "", passport_expiry: "" }
    expect(fields(3, { statutory: empty })).toEqual(["pan_number", "aadhaar_number", "account_holder_name", "account_number", "ifsc_code"])
  })

  it("gives each problem to its own field, in the order the fields appear", () => {
    const issues = validateHireStep(1, withPatch({ employment: { employment_type: "", branch: "", work_email: "nope", annual_ctc: "-5" } }))
    expect(issues.map(issue => issue.field)).toEqual(["employment_type", "branch", "work_email", "annual_ctc"])
  })

  it("never gives one field two messages", () => {
    const issues = validateHireStep(0, withPatch({ firstName: "", email: "bad", phone: "12" }))
    expect(new Set(issues.map(issue => issue.field)).size).toBe(issues.length)
  })
})

describe("identity rules keep their wording", () => {
  it("asks for the required fields", () => {
    expect(issueFor(validateHireStep(0, withPatch({ firstName: " " })), "first_name")).toBe("First name is required.")
    expect(issueFor(validateHireStep(0, withPatch({ dateOfBirth: "" })), "date_of_birth")).toBe("Date of birth is required.")
    expect(issueFor(validateHireStep(0, withPatch({ email: "" })), "email")).toBe("Personal email is required.")
  })

  it("rejects digits in a name but allows hyphens and apostrophes", () => {
    expect(fields(0, { firstName: "As4a" })).toEqual(["first_name"])
    expect(fields(0, { firstName: "Anne-Marie", lastName: "O'Brien" })).toEqual([])
  })

  it("checks the date of birth: future, too young, implausibly old", () => {
    expect(issueFor(validateHireStep(0, withPatch({ dateOfBirth: "2027-01-01" })), "date_of_birth")).toBe("Date of birth cannot be in the future.")
    expect(issueFor(validateHireStep(0, withPatch({ dateOfBirth: "2015-01-01" })), "date_of_birth")).toMatch(/at least 18/)
    expect(issueFor(validateHireStep(0, withPatch({ dateOfBirth: "1900-01-01" })), "date_of_birth")).toMatch(/look right/)
  })

  it("checks the mobile number and an optional alternate one", () => {
    expect(fields(0, { phone: "12345" })).toEqual(["phone"])
    expect(fields(0, { phone: "+91 5876543210" })).toEqual(["phone"])
    expect(fields(0, { alternateMobile: "12" })).toEqual(["alternate_mobile"])
    expect(fields(0, { alternateMobile: "" })).toEqual([])
  })

  it("accepts a valid email and rejects one without a domain", () => {
    expect(fields(0, { email: "a@b.co" })).toEqual([])
    expect(fields(0, { email: "a@b" })).toEqual(["email"])
  })
})

describe("statutory rules", () => {
  const statutory = (patch: Partial<HireSnapshot["statutory"]>) => ({ ...base.statutory, ...patch })
  it("checks the PAN, Aadhaar and IFSC formats", () => {
    expect(fields(3, { statutory: statutory({ pan_number: "ABCDE1234" }) })).toEqual(["pan_number"])
    expect(fields(3, { statutory: statutory({ aadhaar_number: "1234" }) })).toEqual(["aadhaar_number"])
    expect(fields(3, { statutory: statutory({ ifsc_code: "HDFC1234567" }) })).toEqual(["ifsc_code"])
  })
  it("checks the optional UAN and passport dates only when filled in", () => {
    expect(fields(3, { statutory: statutory({ uan_number: "123" }) })).toEqual(["uan_number"])
    expect(fields(3, { statutory: statutory({ passport_issue_date: "2020-05-01", passport_expiry: "2020-04-01" }) })).toEqual(["passport_expiry"])
    expect(fields(3, { statutory: statutory({ passport_issue_date: "2020-05-01", passport_expiry: "2030-05-01" }) })).toEqual([])
  })
})

describe("family, education and documents", () => {
  it("refuses a family member born in the future, and nominee shares over 100%", () => {
    expect(fields(4, { familyEntries: [{ name: "Ravi", date_of_birth: "2030-01-01" }] })).toEqual(["family"])
    expect(fields(4, { nomineeEntries: [{ scheme: "epf_eps", share_percentage: "60" }, { scheme: "epf_eps", share_percentage: "50" }] })).toEqual(["nominees"])
    expect(fields(4, { nomineeEntries: [{ scheme: "epf_eps", share_percentage: "60" }, { scheme: "gratuity", share_percentage: "60" }] })).toEqual([])
  })

  it("asks for at least one qualification, matching the sidebar and the Review step", () => {
    expect(fields(5, { educationEntries: [] })).toEqual(["education"])
    expect(fields(5, { educationEntries: [{ institution: "  " }] })).toEqual(["education"])
  })

  it("names every required document still missing, each against its own row", () => {
    expect(fields(6, { documentTypes: ["pan_card"] })).toEqual(["doc_aadhaar_card", "doc_tenth_certificate", "doc_twelfth_certificate", "doc_degree_certificate"])
    expect(issueFor(validateHireStep(6, withPatch({ documentTypes: [] })), "doc_pan_card")).toBe("PAN Card is required.")
  })

  it("has nothing to check on the steps with no required fields", () => {
    for (const step of [2, 7, 8]) expect(validateHireStep(step, withPatch({ firstName: "" })), `step ${step + 1}`).toEqual([])
  })
})
