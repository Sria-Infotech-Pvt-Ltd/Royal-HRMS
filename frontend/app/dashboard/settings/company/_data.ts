import type { CompanyData, CompanyFieldErrors } from "@/types/company";

// ─── Indian states / UTs ──────────────────────────────────────────────────────

export const STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
  "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
  "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
  "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Andaman and Nicobar Islands", "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
  "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
];

// 2-digit GSTIN state code, mirrors backend `GST_STATE_CODES` in
// apps/accounts/serializers.py — used for a client-side hint only; the
// server is the authority on this check.
export const GST_STATE_CODES: Record<string, string> = {
  "Jammu and Kashmir": "01", "Himachal Pradesh": "02", "Punjab": "03",
  "Chandigarh": "04", "Uttarakhand": "05", "Haryana": "06", "Delhi": "07",
  "Rajasthan": "08", "Uttar Pradesh": "09", "Bihar": "10", "Sikkim": "11",
  "Arunachal Pradesh": "12", "Nagaland": "13", "Manipur": "14", "Mizoram": "15",
  "Tripura": "16", "Meghalaya": "17", "Assam": "18", "West Bengal": "19",
  "Jharkhand": "20", "Odisha": "21", "Chhattisgarh": "22", "Madhya Pradesh": "23",
  "Gujarat": "24", "Dadra and Nagar Haveli and Daman and Diu": "26",
  "Maharashtra": "27", "Karnataka": "29", "Goa": "30", "Lakshadweep": "31",
  "Kerala": "32", "Tamil Nadu": "33", "Puducherry": "34",
  "Andaman and Nicobar Islands": "35", "Telangana": "36", "Andhra Pradesh": "37",
  "Ladakh": "38",
};

export const ENTITY_TYPE_OPTIONS_INDIA = [
  { value: "private_limited",     label: "Private Limited — Pvt Ltd" },
  { value: "public_limited",      label: "Public Limited — Ltd" },
  { value: "llp",                 label: "Limited Liability Partnership — LLP" },
  { value: "partnership",         label: "Partnership Firm" },
  { value: "sole_proprietorship", label: "Sole Proprietorship" },
  { value: "opc",                 label: "One Person Company — OPC" },
];

export const ENTITY_TYPE_OPTIONS_FOREIGN = [
  { value: "corporation",         label: "Corporation (Inc.) — Body corporate" },
  { value: "llc",                 label: "Limited Liability Company — LLC" },
  { value: "foreign_partnership", label: "Partnership" },
  { value: "branch_office",       label: "Branch Office" },
  { value: "other",               label: "Other" },
];

// Entity types that are always incorporated under the Companies Act and
// therefore always carry a CIN — used to conditionally require it.
export const CIN_ENTITY_TYPES = new Set(["private_limited", "public_limited", "opc"]);

export const INDUSTRY_OPTIONS = [
  { value: "it_services",   label: "Information Technology & Services" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "healthcare",    label: "Healthcare" },
  { value: "finance",       label: "Financial Services" },
  { value: "retail",        label: "Retail & E-commerce" },
  { value: "education",     label: "Education" },
  { value: "construction",  label: "Construction & Real Estate" },
  { value: "hospitality",   label: "Hospitality & Travel" },
  { value: "logistics",     label: "Logistics & Transportation" },
  { value: "other",         label: "Other" },
];

export const CURRENCY_OPTIONS = [
  { value: "INR", label: "INR — Indian Rupee (₹)" },
  { value: "USD", label: "USD — US Dollar ($)" },
  { value: "EUR", label: "EUR — Euro (€)" },
  { value: "GBP", label: "GBP — British Pound (£)" },
  { value: "AED", label: "AED — UAE Dirham" },
  { value: "SGD", label: "SGD — Singapore Dollar" },
  { value: "AUD", label: "AUD — Australian Dollar" },
  { value: "CAD", label: "CAD — Canadian Dollar" },
  { value: "JPY", label: "JPY — Japanese Yen" },
  { value: "CNY", label: "CNY — Chinese Yuan" },
];

export const DATE_FORMAT_OPTIONS = [
  { value: "DD-MM-YYYY", label: "DD-MM-YYYY (31-03-2026)" },
  { value: "MM-DD-YYYY", label: "MM-DD-YYYY (03-31-2026)" },
  { value: "YYYY-MM-DD", label: "YYYY-MM-DD (2026-03-31)" },
  { value: "DD/MM/YYYY", label: "DD/MM/YYYY (31/03/2026)" },
];

export const TIMEZONE_OPTIONS = [
  { value: "Asia/Kolkata",         label: "Asia/Kolkata — IST (UTC+5:30)" },
  { value: "Asia/Dubai",           label: "Asia/Dubai — GST (UTC+4:00)" },
  { value: "Asia/Singapore",       label: "Asia/Singapore — SGT (UTC+8:00)" },
  { value: "Europe/London",        label: "Europe/London — GMT/BST" },
  { value: "America/New_York",     label: "America/New_York — ET" },
  { value: "America/Chicago",      label: "America/Chicago — CT" },
  { value: "America/Los_Angeles",  label: "America/Los_Angeles — PT" },
  { value: "Australia/Sydney",     label: "Australia/Sydney — AET" },
];

export const COUNTRY_OPTIONS = [
  { value: "US", label: "United States" },
  { value: "GB", label: "United Kingdom" },
  { value: "AE", label: "United Arab Emirates" },
  { value: "SG", label: "Singapore" },
  { value: "AU", label: "Australia" },
  { value: "CA", label: "Canada" },
  { value: "DE", label: "Germany" },
  { value: "FR", label: "France" },
  { value: "NL", label: "Netherlands" },
  { value: "other", label: "Other" },
];

export const MSME_CLASS_OPTIONS = [
  { value: "micro",          label: "Micro" },
  { value: "small",          label: "Small" },
  { value: "medium",         label: "Medium" },
  { value: "not_registered", label: "Not registered" },
];

export const BANK_ACCOUNT_TYPE_OPTIONS = [
  { value: "savings", label: "Savings" },
  { value: "current", label: "Current" },
];

export const GST_REGISTRATION_TYPE_OPTIONS = [
  { value: "regular",     label: "Regular" },
  { value: "composition", label: "Composition" },
  { value: "casual",      label: "Casual" },
  { value: "other",       label: "Other" },
];

export const EMPTY_COMPANY: CompanyData = {
  jurisdiction: "india", entity_type: "", company_name: "", trade_name: "",
  date_of_incorporation: "", is_listed: false, holding_company_info: "",
  cin: "", roc_jurisdiction: "", pan: "", tan: "",
  country_of_registration: "", registration_number: "", ein: "",
  udyam_msme: "", msme_class: "not_registered", iec: "", epfo_code: "", esic_code: "", professional_tax_reg: "",
  signatory_full_name: "", signatory_designation: "", signatory_din_pan: "",
  signatory_email: "", signatory_appears_on_invoices: true,
  bank_account_holder: "", bank_account_number: "", bank_ifsc: "", bank_account_type: "",
  industry: "", nic_code: "", nature_of_business: "",
  address: "", city: "", state: "", pin_code: "",
  communication_address_same_as_registered: true,
  communication_address: "", communication_city: "", communication_state: "", communication_pin_code: "",
  default_currency: "INR", date_format: "DD-MM-YYYY", timezone: "Asia/Kolkata",
  financial_year_start_month: "April",
  primary_email: "", website: "", official_phone: "",
};

// ─── Financial year ───────────────────────────────────────────────────────────

const MONTH_ORDER = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
] as const;
const MONTH_END_DAY: Record<string, number> = {
  January: 31, February: 28, March: 31, April: 30, May: 31, June: 30,
  July: 31, August: 31, September: 30, October: 31, November: 30, December: 31,
};

export const FINANCIAL_YEAR_OPTIONS = MONTH_ORDER.map(start => {
  const endIdx = (MONTH_ORDER.indexOf(start) + 11) % 12;
  const end = MONTH_ORDER[endIdx];
  const suffix = start === "April" ? " (India standard)" : "";
  return { value: start, label: `1 ${start} – ${MONTH_END_DAY[end]} ${end}${suffix}` };
});

// ─── Entity & Identity — compliance hints, shown once jurisdiction + entity
// type are both picked, mirroring the mockup's contextual banner. ──────────────

export function entityComplianceHint(jurisdiction: string, entityType: string, entityLabel: string): string | null {
  if (!entityType) return null;
  if (jurisdiction === "foreign") {
    return `A foreign ${entityLabel.split(" — ")[0].toLowerCase()} is identified by its local incorporation number and tax ID. India-specific IDs (PAN, GSTIN, TAN) don't apply.`;
  }
  if (CIN_ENTITY_TYPES.has(entityType)) {
    return `A ${entityLabel.split(" — ")[0]} files a CIN and needs directors with DINs. PAN 4th char should be C.`;
  }
  if (entityType === "llp" || entityType === "partnership") {
    return `A ${entityLabel.split(" — ")[0]} doesn't file a CIN with the Registrar of Companies. PAN 4th char should be F.`;
  }
  if (entityType === "sole_proprietorship") {
    return "A Sole Proprietorship uses the proprietor's own PAN (4th char P) — no separate CIN or firm PAN.";
  }
  return null;
}

// ─── CIN — algorithmically parseable, no external lookup needed ───────────────
// Format: L/U + 5-digit industry code + 2-letter state code + 4-digit year +
// 3-letter ownership type + 6-digit registration number.

export function parseCin(cin: string): { listing: string; stateCode: string; year: string } | null {
  const v = cin.trim().toUpperCase();
  if (!CIN_RE.test(v)) return null;
  return {
    listing: v[0] === "L" ? "Listed" : "Unlisted",
    stateCode: v.slice(6, 8),
    year: v.slice(8, 12),
  };
}

// ─── PAN — 4th character always encodes the holder type ───────────────────────

const PAN_HOLDER_TYPES: Record<string, string> = {
  P: "Individual", C: "Company", H: "HUF", A: "AOP", B: "BOI",
  G: "Government", J: "Artificial Judicial Person", L: "Local Authority",
  F: "Firm / LLP", T: "Trust",
};

// Which PAN 4th-character the entity type is expected to carry — used only
// for the "Entity match" hint chip, not a hard validation rule (someone can
// legitimately hold a personal PAN pending a firm PAN, etc).
const ENTITY_EXPECTED_PAN_CHAR: Record<string, string> = {
  private_limited: "C", public_limited: "C", opc: "C",
  llp: "F", partnership: "F",
  sole_proprietorship: "P",
};

export function parsePan(pan: string, entityType: string): { holderChar: string; holderType: string; expectedChar: string | null } | null {
  const v = pan.trim().toUpperCase();
  if (!PAN_RE.test(v)) return null;
  const holderChar = v[3];
  return {
    holderChar,
    holderType: PAN_HOLDER_TYPES[holderChar] ?? "Unknown",
    expectedChar: ENTITY_EXPECTED_PAN_CHAR[entityType] ?? null,
  };
}

// ─── IFSC — first 4 letters are the bank code, remaining 6 are the branch
// code; only the bank-name lookup needs real reference data. ───────────────────

const IFSC_BANK_NAMES: Record<string, string> = {
  SBIN: "State Bank of India", HDFC: "HDFC Bank", ICIC: "ICICI Bank", UTIB: "Axis Bank",
  PUNB: "Punjab National Bank", BARB: "Bank of Baroda", CNRB: "Canara Bank",
  UBIN: "Union Bank of India", IOBA: "Indian Overseas Bank", IDIB: "Indian Bank",
  CBIN: "Central Bank of India", MAHB: "Bank of Maharashtra", UCBA: "UCO Bank",
  PSIB: "Punjab & Sind Bank", KKBK: "Kotak Mahindra Bank", INDB: "IndusInd Bank",
  YESB: "Yes Bank", RATN: "RBL Bank", FDRL: "Federal Bank", SIBL: "South Indian Bank",
  KVBL: "Karur Vysya Bank", TMBL: "Tamilnad Mercantile Bank", CIUB: "City Union Bank",
  DLXB: "Dhanlaxmi Bank", IDFB: "IDFC First Bank", BKID: "Bank of India",
  ESAF: "ESAF Small Finance Bank", EQBL: "Equitas Small Finance Bank",
  UJVN: "Ujjivan Small Finance Bank", AUBL: "AU Small Finance Bank",
  HSBC: "HSBC Bank", SCBL: "Standard Chartered Bank", CITI: "Citibank",
  DBSS: "DBS Bank India", DEUT: "Deutsche Bank",
};

export function resolveIfsc(ifsc: string): { bank: string | null; branchCode: string } | null {
  const v = ifsc.trim().toUpperCase();
  if (!/^[A-Z]{4}0[A-Z0-9]{6}$/.test(v)) return null;
  return { bank: IFSC_BANK_NAMES[v.slice(0, 4)] ?? null, branchCode: v.slice(4) };
}

// ─── GSTIN — live, offline feedback as the row is being typed (format + PAN
// cross-match + state-code cross-match); the server re-checks all of this on
// save, this is only for the "✓ valid · PAN matches" inline hint. ─────────────

export function gstinLiveStatus(gstin: string, companyPan: string, state: string): { ok: boolean; text: string } | null {
  const v = gstin.trim().toUpperCase();
  if (v.length < 15) return null;
  if (!GSTIN_RE.test(v)) return { ok: false, text: "Not a valid GSTIN format." };

  const pan = companyPan.trim().toUpperCase();
  if (pan && v.slice(2, 12) !== pan) {
    return { ok: false, text: `Belongs to PAN ${v.slice(2, 12)}, not the company PAN.` };
  }
  const expectedCode = state ? GST_STATE_CODES[state] : undefined;
  if (expectedCode && v.slice(0, 2) !== expectedCode) {
    return { ok: false, text: `State code ${v.slice(0, 2)} doesn't match ${state}.` };
  }
  return { ok: true, text: pan ? "valid · PAN matches" : "valid format" };
}

// ─── Validators ───────────────────────────────────────────────────────────────

const PAN_RE   = /^[A-Z]{5}\d{4}[A-Z]$/;
const CIN_RE   = /^[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$/;
const TAN_RE   = /^[A-Z]{4}\d{5}[A-Z]$/;
const PIN_RE   = /^\d{6}$/;
const PHONE_RE = /^\+?[\d\s\-()\./]{7,20}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const GSTIN_RE = /^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z1-9]Z[A-Z\d]$/;

export function validateCompany(f: CompanyData, isDraft = false): CompanyFieldErrors {
  const e: CompanyFieldErrors = {};

  if (isDraft) {
    if (f.website && !f.website.startsWith("http://") && !f.website.startsWith("https://"))
      e.website = "Must start with http:// or https://.";
    return e;
  }

  if (!f.company_name.trim()) e.company_name = "Company name is required.";
  if (!f.address.trim())      e.address      = "Address is required.";
  if (!f.city.trim())         e.city         = "City is required.";

  if (f.jurisdiction === "india") {
    if (!f.pan.trim())                              e.pan = "PAN is required for an Indian entity.";
    else if (!PAN_RE.test(f.pan.trim().toUpperCase())) e.pan = "Enter a valid 10-character PAN.";

    if (!f.tan.trim())                              e.tan = "TAN is required for an Indian entity.";
    else if (!TAN_RE.test(f.tan.trim().toUpperCase())) e.tan = "Enter a valid 10-character TAN.";

    if (CIN_ENTITY_TYPES.has(f.entity_type) && !f.cin.trim()) {
      e.cin = "CIN is required for this entity type.";
    } else if (f.cin.trim() && !CIN_RE.test(f.cin.trim().toUpperCase())) {
      e.cin = "Enter a valid CIN (e.g. U74999MH2020PTC123456).";
    }

    if (f.pin_code.trim() && !PIN_RE.test(f.pin_code.trim())) e.pin_code = "PIN code must be exactly 6 digits.";
  } else {
    if (!f.country_of_registration.trim()) e.country_of_registration = "Country of registration is required for a foreign entity.";
    if (!f.registration_number.trim())     e.registration_number     = "Registration number is required for a foreign entity.";
  }

  if (!f.communication_address_same_as_registered) {
    if (!f.communication_address.trim()) e.communication_address = "Communication address is required when it differs from the registered office.";
    if (!f.communication_city.trim())    e.communication_city    = "Communication city is required when it differs from the registered office.";
    if (f.communication_pin_code.trim() && !PIN_RE.test(f.communication_pin_code.trim()))
      e.communication_pin_code = "PIN code must be exactly 6 digits.";
  }

  if (f.website && !f.website.startsWith("http://") && !f.website.startsWith("https://"))
    e.website = "Must start with http:// or https://.";
  if (f.official_phone && !PHONE_RE.test(f.official_phone)) e.official_phone = "Enter a valid phone number.";
  if (f.primary_email && !EMAIL_RE.test(f.primary_email))   e.primary_email  = "Enter a valid email address.";
  if (f.signatory_email && !EMAIL_RE.test(f.signatory_email)) e.signatory_email = "Enter a valid email address.";

  return e;
}

// ─── Profile completeness — a representative subset of fields across every
// card, not an exhaustive one; good enough for a progress indicator. ──────────

const COMPLETION_FIELDS: (keyof CompanyData)[] = [
  "company_name", "entity_type", "date_of_incorporation",
  "address", "city", "state", "pin_code",
  "signatory_full_name", "signatory_designation", "signatory_email",
  "bank_account_holder", "bank_account_number", "bank_ifsc",
  "industry", "primary_email",
];

export function profileCompletionPercent(f: CompanyData): number {
  const jurisdictionFields: (keyof CompanyData)[] = f.jurisdiction === "india"
    ? ["pan", "tan"]
    : ["country_of_registration", "registration_number"];
  const fields = [...COMPLETION_FIELDS, ...jurisdictionFields];
  const filled = fields.filter(k => String(f[k] ?? "").trim().length > 0).length;
  return Math.round((filled / fields.length) * 100);
}
