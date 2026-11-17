// What must be right before the Hire wizard lets a step be left. Pure: no component state, so every rule is unit-tested.
//
// It returns EVERY problem on the step, not just the first. (It used to return one message at a time, so a person fixed a field,
// pressed Next, met the next problem, and so on, over and over.) Each problem carries the key of the field it belongs to, so the
// wizard can mark that field, show the message beside it, and jump to the first one.

import {
  EMAIL_RE, IFSC_RE, MAX_NATIONAL_PHONE_DIGITS, MAX_PLAUSIBLE_AGE_YEARS, MIN_HIRE_AGE_YEARS, MIN_NATIONAL_PHONE_DIGITS,
  MS_PER_YEAR, NAME_RE, PAN_RE,
} from "@/app/dashboard/hire/[hireActionId]/_components/_wizardData"

export interface StepIssue {
  /** Which field the problem belongs to. The wizard finds it again through data-hw-field="<field>". */
  field: string
  message: string
}

/** What the rules read, as plain values. The phone checks are passed in because they live with the phone input. */
export interface HireSnapshot {
  firstName: string
  middleName: string
  lastName: string
  dateOfBirth: string
  gender: string
  nationality: string
  email: string
  phone: string
  alternateMobile: string
  employment: { employment_type: string; branch: string; work_email: string; annual_ctc: string }
  statutory: {
    pan_number: string; aadhaar_number: string; account_holder_name: string; account_number: string; ifsc_code: string
    uan_number: string; passport_issue_date: string; passport_expiry: string
  }
  familyEntries: { name: string; date_of_birth: string }[]
  nomineeEntries: { scheme: string; share_percentage: string }[]
  educationEntries: { institution?: string }[]
  documentTypes: string[]
  requiredDocuments: { key: string; label: string }[]
  phoneDigits: (phone: string) => number
  isPlausiblePhone: (phone: string) => boolean
  now: Date
}

const NAME_MESSAGE = "can only contain letters, spaces, hyphens and apostrophes."

function validateIdentity(s: HireSnapshot): StepIssue[] {
  const issues: StepIssue[] = []
  const add = (field: string, message: string) => issues.push({ field, message })

  if (!s.firstName.trim()) add("first_name", "First name is required.")
  else if (!NAME_RE.test(s.firstName.trim())) add("first_name", `First name ${NAME_MESSAGE}`)
  if (!s.lastName.trim()) add("last_name", "Last name is required.")
  else if (!NAME_RE.test(s.lastName.trim())) add("last_name", `Last name ${NAME_MESSAGE}`)
  if (s.middleName.trim() && !NAME_RE.test(s.middleName.trim())) add("middle_name", `Middle name ${NAME_MESSAGE}`)

  if (!s.dateOfBirth) add("date_of_birth", "Date of birth is required.")
  else {
    const dob = new Date(s.dateOfBirth)
    if (Number.isNaN(dob.getTime())) add("date_of_birth", "Date of birth is not a valid date.")
    else if (dob > s.now) add("date_of_birth", "Date of birth cannot be in the future.")
    else {
      const ageYears = (s.now.getTime() - dob.getTime()) / MS_PER_YEAR
      if (ageYears < MIN_HIRE_AGE_YEARS) add("date_of_birth", `Employee must be at least ${MIN_HIRE_AGE_YEARS} years old.`)
      else if (ageYears > MAX_PLAUSIBLE_AGE_YEARS) add("date_of_birth", "That date of birth doesn't look right — please check it.")
    }
  }

  if (!s.gender) add("gender", "Gender is required.")
  if (!s.nationality.trim()) add("nationality", "Nationality is required.")

  if (!s.email.trim()) add("email", "Personal email is required.")
  else if (!EMAIL_RE.test(s.email.trim())) add("email", "Enter a valid email address.")

  if (!s.phone.trim()) add("phone", "Mobile number is required.")
  else {
    const digits = s.phoneDigits(s.phone)
    if (digits < MIN_NATIONAL_PHONE_DIGITS || digits > MAX_NATIONAL_PHONE_DIGITS) add("phone", "Enter a valid mobile number.")
    else if (!s.isPlausiblePhone(s.phone)) add("phone", "Enter a valid Indian mobile number — it must start with 6-9.")
  }
  if (s.alternateMobile.trim()) {
    const digits = s.phoneDigits(s.alternateMobile)
    if (digits < MIN_NATIONAL_PHONE_DIGITS || digits > MAX_NATIONAL_PHONE_DIGITS) add("alternate_mobile", "Enter a valid alternate mobile number, or leave it blank.")
    else if (!s.isPlausiblePhone(s.alternateMobile)) add("alternate_mobile", "Enter a valid alternate Indian mobile number — it must start with 6-9.")
  }
  return issues
}

function validateEmployment(s: HireSnapshot): StepIssue[] {
  const issues: StepIssue[] = []
  if (!s.employment.employment_type) issues.push({ field: "employment_type", message: "Select an employment type." })
  if (!s.employment.branch) issues.push({ field: "branch", message: "Select a company code." })
  if (s.employment.work_email.trim() && !EMAIL_RE.test(s.employment.work_email.trim())) issues.push({ field: "work_email", message: "Enter a valid work email address." })
  if (s.employment.annual_ctc.trim() && Number(s.employment.annual_ctc) <= 0) issues.push({ field: "annual_ctc", message: "Annual fixed CTC must be greater than zero, or left blank." })
  return issues
}

function validateStatutory(s: HireSnapshot): StepIssue[] {
  const issues: StepIssue[] = []
  const add = (field: string, message: string) => issues.push({ field, message })
  const t = s.statutory
  if (!t.pan_number.trim()) add("pan_number", "PAN is required.")
  else if (!PAN_RE.test(t.pan_number.trim())) add("pan_number", "Enter a valid PAN (format: ABCDE1234F).")
  if (!t.aadhaar_number.trim()) add("aadhaar_number", "Aadhaar is required.")
  else if (t.aadhaar_number.trim().length !== 12) add("aadhaar_number", "Aadhaar must be exactly 12 digits.")
  if (!t.account_holder_name.trim()) add("account_holder_name", "Account holder name is required.")
  else if (!NAME_RE.test(t.account_holder_name.trim())) add("account_holder_name", `Account holder name ${NAME_MESSAGE}`)
  if (!t.account_number.trim()) add("account_number", "Account number is required.")
  else if (t.account_number.trim().length < 6) add("account_number", "Enter a valid account number.")
  if (!t.ifsc_code.trim()) add("ifsc_code", "IFSC code is required.")
  else if (!IFSC_RE.test(t.ifsc_code.trim())) add("ifsc_code", "Enter a valid IFSC code (format: HDFC0001234).")
  if (t.uan_number.trim() && t.uan_number.trim().length !== 12) add("uan_number", "UAN must be 12 digits")
  if (t.passport_issue_date && t.passport_expiry && t.passport_expiry <= t.passport_issue_date) add("passport_expiry", "Passport expiry must be after the issue date.")
  return issues
}

function validateFamily(s: HireSnapshot): StepIssue[] {
  const issues: StepIssue[] = []
  // A father with a date of birth in the future used to be accepted with no check at all.
  const badDob = s.familyEntries.find(entry => {
    if (!entry.date_of_birth) return false
    const date = new Date(entry.date_of_birth)
    return Number.isNaN(date.getTime()) || date > s.now
  })
  if (badDob) issues.push({ field: "family", message: `${badDob.name || "A family member"}'s date of birth cannot be in the future.` })

  const totals: Record<string, number> = {}
  for (const nominee of s.nomineeEntries) {
    const scheme = nominee.scheme || "epf_eps"
    totals[scheme] = (totals[scheme] ?? 0) + (Number(nominee.share_percentage) || 0)
  }
  const over = Object.entries(totals).find(([, total]) => total > 100)
  if (over) issues.push({ field: "nominees", message: `Nominee shares for ${over[0]} add up to ${over[1]}% — they can't exceed 100%.` })
  return issues
}

function validateEducation(s: HireSnapshot): StepIssue[] {
  // The sidebar already marks this step as needing one entry, and the Review step refuses a hire without one.
  if (s.educationEntries.some(entry => entry.institution?.trim())) return []
  return [{ field: "education", message: "Add at least one qualification, with the institution, before continuing." }]
}

function validateDocuments(s: HireSnapshot): StepIssue[] {
  const uploaded = new Set(s.documentTypes)
  return s.requiredDocuments
    .filter(document => !uploaded.has(document.key))
    .map(document => ({ field: `doc_${document.key}`, message: `${document.label} is required.` }))
}

/** Every problem on step `step` (0-based), in the order the fields appear. Empty when the step may be left. */
export function validateHireStep(step: number, snapshot: HireSnapshot): StepIssue[] {
  switch (step) {
    case 0: return validateIdentity(snapshot)
    case 1: return validateEmployment(snapshot)
    case 3: return validateStatutory(snapshot)
    case 4: return validateFamily(snapshot)
    case 5: return validateEducation(snapshot)
    case 6: return validateDocuments(snapshot)
    default: return []
  }
}

/** The message for one field, or undefined. */
export function issueFor(issues: StepIssue[], field: string): string | undefined {
  return issues.find(issue => issue.field === field)?.message
}
