// Monthly pay breakup (earnings, employer contributions, statutory deductions) derived from an annual CTC —
// the same rules the Employee Directory reference uses in its Basic pay dialog. Pure functions, no I/O.
//
// This is the breakup HR sees and may override line by line; it describes the pay record. The payroll run
// itself still computes from the salary structure assigned to the employee.

export type OverrideKey = string
export type EarningOverrides = Partial<Record<OverrideKey, number>>

export interface PayStructureComponent {
  id: string
  code: string
  name: string
  component_type: "earning" | "deduction" | "allowance"
  calculation_type:
    | "percentage_of_ctc"
    | "percentage_of_basic"
    | "percentage_of_basic_plus_da"
    | "fixed"
    | "balance_to_ctc"
    | "metro_hra_of_basic"
  value: string
  is_taxable: boolean
  is_active: boolean
  order: number
  effective_from: string
  reset_override: boolean
}

export const PAY_BREAKUP_LINE_GROUPS = [
  {
    label: "Earnings",
    lines: [
      { code: "1000", name: "Basic Pay" },
      { code: "1010", name: "Dearness Allowance" },
      { code: "1100", name: "House Rent Allowance" },
      { code: "1200", name: "Conveyance Allowance" },
      { code: "1300", name: "Medical Allowance" },
      { code: "1350", name: "Leave Travel Allowance" },
      { code: "1400", name: "Special Allowance" },
    ],
  },
  {
    label: "Employer Contributions",
    lines: [
      { code: "5000", name: "Employer PF (EPF)" },
      { code: "5010", name: "Employer Pension (EPS)" },
      { code: "5100", name: "Gratuity Provision" },
      { code: "5200", name: "Employer ESI" },
    ],
  },
  {
    label: "Statutory Deductions",
    lines: [
      { code: "6000", name: "Employee PF" },
      { code: "6100", name: "Employee ESI" },
      { code: "6200", name: "Professional Tax" },
    ],
  },
] as const

export const DEFAULT_VISIBLE_PAY_LINE_CODES = PAY_BREAKUP_LINE_GROUPS.flatMap(
  group => group.lines.map(line => line.code),
)

export interface PayLine {
  code: string
  name: string
  amount: number
  editable: boolean
  /** Present only on editable earnings — the key an override is stored under. */
  key?: OverrideKey
  note: string
  structureComponent?: boolean
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
  /** Active, effective salary components. Omit only for the legacy default preview. */
  components?: PayStructureComponent[]
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
  if (options.components !== undefined) {
    return buildStructurePay(monthlyCtc, options, options.components)
  }
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

  function buildStructurePay(
    monthlyCtc: number,
    options: PayOptions,
    components: PayStructureComponent[],
  ): PayBreakup {
    const metro = options.isMetroLocation ?? false
    const state = options.professionalTaxState ?? "Telangana"
    const overrides = options.overrides ?? {}
    const active = components.filter(component => component.is_active).slice().sort((a, b) => a.order - b.order)
    const byName = (name: string) => active.find(component => component.name.toLowerCase() === name)
    const basicComponent = byName("basic")
    const daComponent = byName("da") ?? byName("dearness allowance")
    const basic = basicComponent ? componentAmount(basicComponent, monthlyCtc, 0, 0, metro, overrides) : 0
    const da = daComponent ? componentAmount(daComponent, monthlyCtc, basic, 0, metro, overrides) : 0
    const basicPlusDa = basic + da
    const earnings: PayLine[] = []
    const deductions: PayLine[] = []
    let earningsBeforeBalance = basic
    const balanceComponents: PayStructureComponent[] = []

    for (const component of active) {
      const normalizedName = component.name.toLowerCase()
      if (normalizedName === "basic" || normalizedName === "da" || normalizedName === "dearness allowance") continue
      if (component.calculation_type === "balance_to_ctc") {
        balanceComponents.push(component)
        continue
      }
      const amount = componentAmount(component, monthlyCtc, basic, basicPlusDa, metro, overrides)
      const note = calculationNote(component)
      const line: PayLine = {
        code: component.code,
        name: component.name,
        amount,
        editable: component.component_type !== "deduction",
        ...(component.component_type !== "deduction" ? { key: component.code } : {}),
        note,
        structureComponent: true,
      }
      if (component.component_type === "deduction") {
        deductions.push({ ...line, editable: true, key: component.code })
      } else {
        earnings.push(line)
        earningsBeforeBalance += amount
      }
    }

    if (basicComponent) {
      earnings.unshift({
        code: basicComponent.code,
        name: basicComponent.name,
        amount: basic,
        editable: true,
        key: basicComponent.code,
        note: calculationNote(basicComponent),
        structureComponent: true,
      })
    }
    if (daComponent) {
      earnings.splice(basicComponent ? 1 : 0, 0, {
        code: daComponent.code,
        name: daComponent.name,
        amount: da,
        editable: true,
        key: daComponent.code,
        note: calculationNote(daComponent),
        structureComponent: true,
      })
      earningsBeforeBalance += da
    }

    let gross = earningsBeforeBalance
    let employerPf = 0
    let eps = 0
    let gratuity = 0
    let employerEsi = 0
    let employeePf = 0
    let employeeEsi = 0
    let tax = 0
    if (balanceComponents.length > 0) {
      for (let attempt = 0; attempt < 5; attempt += 1) {
        const pfWage = Math.min(basicPlusDa, PF_CEILING)
        eps = rupees(pfWage * 0.0833)
        employerPf = rupees(pfWage * 0.12) - eps
        gratuity = rupees(basicPlusDa * 0.0481)
        employerEsi = gross <= ESI_LIMIT ? rupees(gross * 0.0325) : 0
        const balance = Math.max(0, monthlyCtc - earningsBeforeBalance - employerPf - eps - gratuity - employerEsi)
        gross = earningsBeforeBalance + balance
      }
      const balanceComponent = balanceComponents[0]
      const balanceAmount = Math.max(0, gross - earningsBeforeBalance)
      const balanceLine: PayLine = {
        code: balanceComponent.code,
        name: balanceComponent.name,
        amount: balanceAmount,
        editable: false,
        note: "Balances earnings to CTC after statutory employer contributions",
        structureComponent: true,
      }
      if (balanceComponent.component_type === "deduction") deductions.push(balanceLine)
      else earnings.push(balanceLine)
      for (const component of balanceComponents.slice(1)) {
        if (component.component_type === "deduction") {
          deductions.push({ ...balanceLine, code: component.code, name: component.name, amount: 0 })
        } else {
          earnings.push({ ...balanceLine, code: component.code, name: component.name, amount: 0 })
        }
      }
    } else {
      gross = earningsBeforeBalance
    }

    const pfWage = Math.min(basicPlusDa, PF_CEILING)
    eps = rupees(pfWage * 0.0833)
    employerPf = rupees(pfWage * 0.12) - eps
    gratuity = rupees(basicPlusDa * 0.0481)
    const esiApplies = gross <= ESI_LIMIT
    employerEsi = esiApplies ? rupees(gross * 0.0325) : 0
    employeeEsi = esiApplies ? rupees(gross * 0.0075) : 0
    employeePf = rupees(pfWage * 0.12)
    tax = professionalTax(state, gross)

    const customDeductions = deductions.reduce((total, line) => total + line.amount, 0)
    deductions.push(
      { code: "6000", name: "Employee PF", amount: employeePf, editable: false, note: "12% of Basic+DA, ₹15,000 ceiling" },
      { code: "6100", name: "Employee ESI", amount: employeeEsi, editable: false, note: esiApplies ? "0.75% of gross" : "Not applicable" },
      { code: "6200", name: "Professional Tax", amount: tax, editable: false, note: `${state} slab` },
    )
    const employerTotal = employerPf + eps + gratuity + employerEsi
    const deductionTotal = customDeductions + employeePf + employeeEsi + tax
    return {
      earnings,
      employer: [
        { code: "5000", name: "Employer PF (EPF)", amount: employerPf, editable: false, note: "3.67% of Basic+DA, ₹15,000 ceiling" },
        { code: "5010", name: "Employer Pension (EPS)", amount: eps, editable: false, note: "8.33% of Basic+DA, ₹15,000 ceiling" },
        { code: "5100", name: "Gratuity Provision", amount: gratuity, editable: false, note: "4.81% of Basic+DA" },
        { code: "5200", name: "Employer ESI", amount: employerEsi, editable: false, note: esiApplies ? "3.25% of gross" : "Gross above ₹21,000 — not applicable" },
      ],
      deductions,
      gross,
      employerTotal,
      deductionTotal,
      monthlyCtc: gross + employerTotal,
      net: gross - deductionTotal,
    }
  }

  function componentAmount(
    component: PayStructureComponent,
    monthlyCtc: number,
    basic: number,
    basicPlusDa: number,
    metro: boolean,
    overrides: EarningOverrides,
  ): number {
    let amount: number
    switch (component.calculation_type) {
      case "percentage_of_ctc":
        amount = rupees(monthlyCtc * Number(component.value) / 100)
        break
      case "percentage_of_basic":
        amount = rupees(basic * Number(component.value) / 100)
        break
      case "percentage_of_basic_plus_da":
        amount = rupees(basicPlusDa * Number(component.value) / 100)
        break
      case "metro_hra_of_basic":
        amount = rupees(basic * (metro ? 0.5 : 0.4))
        break
      case "fixed":
        amount = rupees(Number(component.value))
        break
      case "balance_to_ctc":
        amount = 0
        break
    }
    const alias = {
      basic: "basic",
      da: "da",
      "dearness allowance": "da",
      hra: "hra",
      "conveyance allowance": "conv",
      "medical allowance": "med",
      "leave travel allowance": "lta",
    }[component.name.toLowerCase()]
    const override = overrides[component.code] ?? (alias ? overrides[alias] : undefined)
    return override === undefined ? amount : Math.max(0, Math.round(override))
  }

  function calculationNote(component: PayStructureComponent): string {
    switch (component.calculation_type) {
      case "percentage_of_ctc": return `${component.value}% of CTC`
      case "percentage_of_basic": return `${component.value}% of Basic`
      case "percentage_of_basic_plus_da": return `${component.value}% of Basic+DA`
      case "metro_hra_of_basic": return "50% / 40% of Basic by location"
      case "balance_to_ctc": return "Balances earnings to CTC"
      case "fixed": return "Fixed monthly amount"
    }
  }
}

/**
 * The breakup rounds to whole monthly rupees, so `monthlyCtc * 12` drifts from the CTC the user typed
 * (400000 -> 399996). With no earnings overrides the breakup is only a display of how the typed CTC splits,
 * so the typed value is what to save and show. With overrides the real total can differ from what was typed,
 * so the re-summed breakup is the correct annual figure.
 */
export function annualCtcToSave(enteredAnnualCtc: number, breakupMonthlyCtc: number, hasOverrides: boolean): number {
  return hasOverrides ? breakupMonthlyCtc * 12 : Math.round(enteredAnnualCtc)
}
