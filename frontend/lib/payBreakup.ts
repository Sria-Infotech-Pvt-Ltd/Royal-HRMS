// Monthly pay breakup (earnings, employer contributions, statutory deductions) derived from an annual CTC —
// the same rules the Employee Directory reference uses in its Basic pay dialog. Pure functions, no I/O.
//
// This is the breakup HR sees and may override line by line; it describes the pay record. The payroll run
// itself still computes from the salary structure assigned to the employee.

export type OverrideKey = "basic" | "da" | "hra" | "conv" | "med" | "lta"
export type EarningOverrides = Partial<Record<OverrideKey, number>>

export interface PayLine {
  code: string
  name: string
  amount: number
  editable: boolean
  /** Present only on editable earnings — the key an override is stored under. */
  key?: OverrideKey
  note: string
}

export interface PayBreakup {
  earnings: PayLine[]
  employer: PayLine[]
  deductions: PayLine[]
  gross: number
  employerTotal: number
  deductionTotal: number
  monthlyCtc: number
  net: number
}

export interface PayOptions {
  /** Basic as a percentage of monthly CTC (40, 45 or 50). */
  basicPercent?: number
  /** Metro cities get a 50% HRA exemption, everywhere else 40%. */
  isMetroLocation?: boolean
  professionalTaxState?: string
  overrides?: EarningOverrides
}

const PF_CEILING = 15000
const ESI_LIMIT = 21000
const METROS = ["Delhi", "Mumbai", "Kolkata", "Chennai"]

export function isMetro(location: string): boolean {
  return METROS.some(city => location.includes(city))
}

/** Professional-tax state for a work location (default Telangana, where the company is based). */
export function professionalTaxState(location: string): string {
  if (/bengaluru|bangalore|karnataka|whitefield/i.test(location)) return "Karnataka"
  if (/pune|mumbai|maharashtra/i.test(location)) return "Maharashtra"
  return "Telangana"
}

function professionalTax(state: string, gross: number): number {
  if (state === "Telangana") return gross >= 20000 ? 200 : gross >= 15000 ? 150 : 0
  if (state === "Karnataka") return gross >= 25000 ? 200 : 0
  if (state === "Maharashtra") return gross > 10000 ? 200 : gross > 7500 ? 175 : 0
  return 0
}

const rupees = (value: number) => Math.round(value)

export function buildPay(monthlyCtc: number, options: PayOptions = {}): PayBreakup {
  const percent = options.basicPercent ?? 40
  const metro = options.isMetroLocation ?? false
  const state = options.professionalTaxState ?? "Telangana"
  const overrides = options.overrides ?? {}

  const basic = overrides.basic ?? rupees(monthlyCtc * (percent / 100))
  const da = overrides.da ?? 0
  const basicPlusDa = basic + da
  const hra = overrides.hra ?? rupees(basicPlusDa * (metro ? 0.5 : 0.4))
  const conveyance = overrides.conv ?? 1600
  const medical = overrides.med ?? 1250
  const lta = overrides.lta ?? rupees(basicPlusDa * 0.0833)

  const pfWage = Math.min(basicPlusDa, PF_CEILING)
  const eps = rupees(pfWage * 0.0833)
  const employerPf = rupees(pfWage * 0.12) - eps
  const gratuity = rupees(basicPlusDa * 0.0481)
  const employerFixed = employerPf + eps + gratuity
  const special = Math.max(0, monthlyCtc - employerFixed - (basicPlusDa + hra + conveyance + medical + lta))
  const gross = basicPlusDa + hra + conveyance + medical + lta + special

  const esiApplies = gross <= ESI_LIMIT
  const employerEsi = esiApplies ? rupees(gross * 0.0325) : 0
  const employeeEsi = esiApplies ? rupees(gross * 0.0075) : 0
  const employeePf = rupees(pfWage * 0.12)
  const tax = professionalTax(state, gross)

  return {
    earnings: [
      { code: "1000", name: "Basic Pay", amount: basic, editable: true, key: "basic", note: `${percent}% of CTC` },
      { code: "1010", name: "Dearness Allowance", amount: da, editable: true, key: "da", note: "Counts as wages with Basic" },
      { code: "1100", name: "House Rent Allowance", amount: hra, editable: true, key: "hra", note: `${metro ? "50%" : "40%"} of Basic+DA — ${metro ? "metro" : "non-metro"}` },
      { code: "1200", name: "Conveyance Allowance", amount: conveyance, editable: true, key: "conv", note: "Legacy — subsumed into standard deduction" },
      { code: "1300", name: "Medical Allowance", amount: medical, editable: true, key: "med", note: "Legacy — subsumed into standard deduction" },
      { code: "1350", name: "Leave Travel Allowance", amount: lta, editable: true, key: "lta", note: "8.33% of Basic+DA" },
      { code: "1400", name: "Special Allowance", amount: special, editable: false, note: "Balances earnings to CTC" },
    ],
    employer: [
      { code: "5000", name: "Employer PF (EPF)", amount: employerPf, editable: false, note: "3.67% of Basic+DA, ₹15,000 ceiling" },
      { code: "5010", name: "Employer Pension (EPS)", amount: eps, editable: false, note: "8.33% of Basic+DA, ₹15,000 ceiling" },
      { code: "5100", name: "Gratuity Provision", amount: gratuity, editable: false, note: "4.81% of Basic+DA" },
      { code: "5200", name: "Employer ESI", amount: employerEsi, editable: false, note: esiApplies ? "3.25% of gross" : "Gross above ₹21,000 — not applicable" },
    ],
    deductions: [
      { code: "6000", name: "Employee PF", amount: employeePf, editable: false, note: "12% of Basic+DA, ₹15,000 ceiling" },
      { code: "6100", name: "Employee ESI", amount: employeeEsi, editable: false, note: esiApplies ? "0.75% of gross" : "Not applicable" },
      { code: "6200", name: "Professional Tax", amount: tax, editable: false, note: `${state} slab` },
    ],
    gross,
    employerTotal: employerPf + eps + gratuity + employerEsi,
    deductionTotal: employeePf + employeeEsi + tax,
    monthlyCtc: gross + employerPf + eps + gratuity + employerEsi,
    net: gross - (employeePf + employeeEsi + tax),
  }
}
