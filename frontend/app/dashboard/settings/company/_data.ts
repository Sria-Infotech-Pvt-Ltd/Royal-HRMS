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
  { value: "opc",                 label: "One Person Company — OPC" },
  { value: "llp",                 label: "LLP — Partnership" },
  { value: "partnership",         label: "Partnership Firm — Firm" },
  { value: "sole_proprietorship", label: "Proprietorship — Sole owner" },
  { value: "huf",                 label: "HUF — Family" },
  { value: "section8",            label: "Section 8 — Non-profit" },
  { value: "trust_society",       label: "Trust / Society — Charitable" },
];

export const ENTITY_TYPE_OPTIONS_FOREIGN = [
  { value: "corporation",         label: "Corporation (Inc.) — Body corporate" },
  { value: "llc",                 label: "Limited Liability Company — LLC" },
  { value: "foreign_partnership", label: "Partnership" },
  { value: "branch_office",       label: "Branch Office" },
  { value: "other",               label: "Other" },
];

// Entity types that are always incorporated under the Companies Act and
// therefore always carry a CIN — used to conditionally require it. A
// Section 8 company is still a company under the Act (just non-profit), so
// it carries a CIN too; HUF/proprietorship/trust/society don't.
export const CIN_ENTITY_TYPES = new Set(["private_limited", "public_limited", "opc", "section8"]);

// CIN's embedded "ownership class" (3 letters right after the year, e.g. the
// PTC in U74999MH2020PTC123456) reliably maps to entity type for these three
// — MCA introduced OPC as its own class specifically so it's unambiguous,
// and PTC/PLC are like this consistently across the ROC record. Section 8 is
// deliberately excluded: it's a *license* layered onto an otherwise-normal
// private/public company, so its CIN class is still PTC/PLC/OPC depending on
// the underlying company type, not a class of its own — asserting one exact
// value for it would be as likely to be wrong as right.
const CIN_CLASS_BY_ENTITY: Record<string, string> = {
  private_limited: "PTC", public_limited: "PLC", opc: "OPC",
};

// Only a Public Limited company can legally be listed (CIN prefix "L") — a
// Private Limited/OPC/Section 8 company is structurally barred from public
// listing, so an "L" prefix on one of these is never valid, regardless of
// what the rest of the CIN says.
const CIN_CANNOT_BE_LISTED_ENTITY_TYPES = new Set(["private_limited", "opc", "section8"]);

// CIN's embedded state code (e.g. the MH in U74999MH2020PTC123456) is MCA's
// own 2-LETTER ROC abbreviation — a completely different coding system from
// GSTIN's 2-DIGIT numeric state code (GST_STATE_CODES above), not the same
// table reused. Chhattisgarh and Uttarakhand have seen more than one
// abbreviation in real CINs over the years (CG/CT and UT/UK respectively,
// from ROC jurisdiction renames) — using the current, more common variant
// for each; a false mismatch on an older CIN from one of those two states is
// a known residual gap, not a silent wrong assumption.
const ROC_STATE_CODES: Record<string, string> = {
  "Andaman and Nicobar Islands": "AN", "Andhra Pradesh": "AP", "Arunachal Pradesh": "AR",
  "Assam": "AS", "Bihar": "BR", "Chandigarh": "CH", "Chhattisgarh": "CG",
  "Dadra and Nagar Haveli and Daman and Diu": "DN", "Delhi": "DL", "Goa": "GA",
  "Gujarat": "GJ", "Haryana": "HR", "Himachal Pradesh": "HP", "Jammu and Kashmir": "JK",
  "Jharkhand": "JH", "Karnataka": "KA", "Kerala": "KL", "Ladakh": "LA",
  "Lakshadweep": "LD", "Madhya Pradesh": "MP", "Maharashtra": "MH", "Manipur": "MN",
  "Meghalaya": "ML", "Mizoram": "MZ", "Nagaland": "NL", "Odisha": "OR",
  "Puducherry": "PY", "Punjab": "PB", "Rajasthan": "RJ", "Sikkim": "SK",
  "Tamil Nadu": "TN", "Telangana": "TG", "Tripura": "TR", "Uttar Pradesh": "UP",
  "Uttarakhand": "UT", "West Bengal": "WB",
};

// The single `cin` column is reused for whatever this entity type's actual
// registration number is called. Label/required/format follow the approved
// design reference (india-company-profile-v2 artifact's TYPES_IN +
// applyEntityType()/validateRegNo()) exactly: every entity type that has a
// registration number at all (CIN types, LLP, Partnership, Trust/Society)
// requires it — only Proprietorship/HUF have none, where `null` means the
// field is hidden entirely, not just optional.
export interface RegistrationNumberConfig { label: string; required: boolean; placeholder: string }
export const REGISTRATION_NUMBER_CONFIG: Record<string, RegistrationNumberConfig | null> = {
  private_limited:      { label: "CIN",              required: true, placeholder: "U74999MH2020PTC123456" },
  public_limited:       { label: "CIN",              required: true, placeholder: "U74999MH2020PTC123456" },
  opc:                  { label: "CIN",              required: true, placeholder: "U74999MH2020PTC123456" },
  section8:             { label: "CIN",              required: true, placeholder: "U74999MH2020PTC123456" },
  llp:                  { label: "LLPIN",            required: true, placeholder: "AAB-1234" },
  partnership:          { label: "Registration No.", required: true, placeholder: "Registration number from your certificate" },
  trust_society:        { label: "Registration No.", required: true, placeholder: "Registration number from your certificate" },
  sole_proprietorship:  null,
  huf:                  null,
};

// The "Directors" table's title, ID-column label, and ID format all follow
// who this entity type's PEOPLE actually are — DIN for company Directors,
// DPIN for an LLP's Designated Partners (both real-world 8-digit numeric
// IDs — India's MCA unified the two numbering systems years ago, so one
// "din" format covers both), PAN for Partnership/Trust (no personal-ID
// system for a firm partner or trustee, so the artifact uses their PAN
// instead — a 10-character alphanumeric code the old hardcoded
// 8-digit-numeric-only input would have silently rejected). Proprietorship/
// HUF have no such table at all (`null` hides the whole section, matching
// REGISTRATION_NUMBER_CONFIG's convention above). Foreign entity types
// don't map 1:1 onto the design reference's own foreign type list (this
// app's foreign types are corporation/llc/foreign_partnership/branch_office/
// other, not the reference's finer-grained set) — best-effort adapted
// rather than a literal artifact match for those five.
export interface PeopleConfig { sectionTitle: string; idLabel: string; idFormat: "din" | "pan" | "free"; singular: string }
export const PEOPLE_CONFIG: Record<string, PeopleConfig | null> = {
  private_limited:      { sectionTitle: "Directors",           idLabel: "DIN",         idFormat: "din",  singular: "director" },
  public_limited:       { sectionTitle: "Directors",           idLabel: "DIN",         idFormat: "din",  singular: "director" },
  opc:                   { sectionTitle: "Directors",           idLabel: "DIN",         idFormat: "din",  singular: "director" },
  section8:              { sectionTitle: "Directors",           idLabel: "DIN",         idFormat: "din",  singular: "director" },
  llp:                   { sectionTitle: "Designated Partners",  idLabel: "DPIN",        idFormat: "din",  singular: "designated partner" },
  partnership:           { sectionTitle: "Partners",             idLabel: "PAN",         idFormat: "pan",  singular: "partner" },
  trust_society:         { sectionTitle: "Trustees",             idLabel: "PAN",         idFormat: "pan",  singular: "trustee" },
  sole_proprietorship:   null,
  huf:                   null,
  // Foreign — best-effort, see note above.
  corporation:           { sectionTitle: "Directors",           idLabel: "Director ID", idFormat: "free", singular: "director" },
  llc:                   { sectionTitle: "Members / Managers",  idLabel: "Member ID",   idFormat: "free", singular: "member/manager" },
  foreign_partnership:   { sectionTitle: "Partners",             idLabel: "Partner ID",  idFormat: "free", singular: "partner" },
  branch_office:         null,
  other:                 { sectionTitle: "Directors",           idLabel: "Director ID", idFormat: "free", singular: "director" },
};

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
  if (entityType === "llp") {
    return "An LLP doesn't file a CIN — it's identified by its LLPIN, filed under the LLP Act rather than the Companies Act. PAN 4th char should be F.";
  }
  if (entityType === "partnership") {
    return "A Partnership Firm doesn't file a CIN — enter its registration number from the certificate instead. PAN 4th char should be F.";
  }
  if (entityType === "sole_proprietorship") {
    return "A Proprietorship uses the proprietor's own PAN (4th char P) — no separate CIN or firm PAN.";
  }
  if (entityType === "huf") {
    return "An HUF isn't registered under the Companies Act — no CIN. It's identified by its own HUF PAN (4th char H) and the karta's details.";
  }
  if (entityType === "trust_society") {
    return "A Trust or Society is registered under trust/society law, not the Companies Act — no CIN. Identified by its own PAN (4th char T for a Trust, A for a Society) and registration certificate.";
  }
  return null;
}

// ─── CIN — algorithmically parseable, no external lookup needed ───────────────
// Format: L/U + 5-digit industry code + 2-letter state code + 4-digit year +
// 3-letter ownership type + 6-digit registration number.

export function parseCin(cin: string): { listing: string; stateCode: string; year: string; classCode: string } | null {
  const v = cin.trim().toUpperCase();
  if (!CIN_RE.test(v)) return null;
  return {
    listing: v[0] === "L" ? "Listed" : "Unlisted",
    stateCode: v.slice(6, 8),
    year: v.slice(8, 12),
    classCode: v.slice(12, 15),
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
  private_limited: "C", public_limited: "C", opc: "C", section8: "C",
  llp: "F", partnership: "F",
  sole_proprietorship: "P",
  huf: "H",
  // trust_society deliberately unmapped — a Trust's PAN 4th char is "T" but
  // a Society's is "A"; this one dropdown option covers both, so there's no
  // single correct expected character to check against.
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

// ─── GSTIN checksum — the 15th character is a check digit over the first 14,
// a Luhn-like algorithm in base 36 (0-9 then A-Z). Publicly documented GSTN
// spec; verified here against the two independently-known-valid GSTINs used
// elsewhere in this file/the defect report before being relied on. ───────────

const GSTIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

function gstinCheckDigit(first14: string): string {
  const len = GSTIN_CHARSET.length;
  let factor = 2;
  let sum = 0;
  for (let i = first14.length - 1; i >= 0; i--) {
    const code = GSTIN_CHARSET.indexOf(first14[i]);
    let d = factor * code;
    d = Math.floor(d / len) + (d % len);
    sum += d;
    factor = factor === 2 ? 1 : 2;
  }
  return GSTIN_CHARSET[(len - (sum % len)) % len];
}

// A GSTIN's own state code (first 2 digits) must be one of the 38 real codes
// — distinguishing "not a real code at all" from "a real code, just not the
// one for the selected state" is worth doing since the two mean different
// things (garbage input vs. a state mismatch).
const VALID_GST_STATE_CODES = new Set(Object.values(GST_STATE_CODES));

// ─── GSTIN — live, offline feedback as the row is being typed (format +
// checksum + PAN cross-match + state-code cross-match); the server re-checks
// all of this on save, this is only for the "✓ valid · PAN matches" inline
// hint. ─────────────────────────────────────────────────────────────────────

export function gstinLiveStatus(gstin: string, companyPan: string, state: string): { ok: boolean; text: string } | null {
  const v = gstin.trim().toUpperCase();
  if (v.length < 15) return null;
  if (!GSTIN_RE.test(v)) return { ok: false, text: "Not a valid GSTIN format." };
  if (gstinCheckDigit(v.slice(0, 14)) !== v[14]) {
    return { ok: false, text: "Invalid GSTIN checksum — check for a typo." };
  }
  if (!VALID_GST_STATE_CODES.has(v.slice(0, 2))) {
    return { ok: false, text: `${v.slice(0, 2)} isn't a valid GST state code.` };
  }

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
const DIN_RE   = /^\d{8}$/;
const UDYAM_RE = /^UDYAM-[A-Z]{2}-\d{2}-\d{7}$/;
const ESIC_RE  = /^\d{17}$/;
// LLPIN format per the approved design reference (india-company-profile-v2
// artifact's validateRegNo()) — 3 letters, an optional hyphen, 4 digits
// (e.g. AAB-1234).
const LLPIN_RE = /^[A-Z]{3}-?\d{4}$/;
// EPFO establishment codes and state Professional Tax registration numbers
// have no single nationally-standardized format (same reasoning as the
// backend's matching constant in serializers.py) — this only guards against
// garbage input, not a specific shape.
const LOOSE_REGISTRATION_RE = /^[A-Z0-9/\-]{1,30}$/;
// Requires an actual http(s) scheme AND a real-looking domain after it — a
// plain startsWith("http") check still lets a scheme-confusion payload like
// "http://x/\njavascript:alert(1)" through; this shape-checks the whole
// string instead of just its prefix.
const WEBSITE_RE = /^https?:\/\/[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+(:\d{1,5})?(\/\S*)?$/;
// Indian postal PINs never start with 0 (the leading digit encodes one of 9
// postal regions, 1-9) — a bare \d{6} check happily accepts "000000".
const PIN_LEADING_ZERO_RE = /^0/;
// No Indian company law predates the 1850s, and a date of incorporation
// obviously can't be in the future — generous floor/ceiling, not a strict
// business-rule boundary, just enough to catch fat-finger dates like 1800
// or 2030.
const MIN_INCORPORATION_DATE = "1850-01-01";

function isValidPin(v: string): boolean {
  return PIN_RE.test(v) && !PIN_LEADING_ZERO_RE.test(v);
}

export function validateCompany(f: CompanyData, isDraft = false): CompanyFieldErrors {
  const e: CompanyFieldErrors = {};

  if (isDraft) {
    if (f.website && !WEBSITE_RE.test(f.website.trim()))
      e.website = "Enter a full URL starting with http:// or https://.";
    return e;
  }

  if (!f.company_name.trim()) e.company_name = "Company name is required.";
  if (!f.address.trim())      e.address      = "Address is required.";
  if (!f.city.trim())         e.city         = "City is required.";

  if (f.jurisdiction === "india") {
    if (!f.pan.trim())                              e.pan = "PAN is required for an Indian entity.";
    else if (!PAN_RE.test(f.pan.trim().toUpperCase())) e.pan = "Enter a valid 10-character PAN.";

    // TAN is intentionally NOT required here, for any entity type — matches
    // the approved design reference, which marks it "(for TDS)"/optional
    // throughout and never makes it required per entity type. Format is
    // still checked whenever a value is actually entered.
    if (f.tan.trim() && !TAN_RE.test(f.tan.trim().toUpperCase())) e.tan = "Enter a valid 10-character TAN.";

    const regConfig = REGISTRATION_NUMBER_CONFIG[f.entity_type] ?? null;
    if (regConfig) {
      if (regConfig.required && !f.cin.trim()) {
        e.cin = `${regConfig.label} is required for this entity type.`;
      } else if (f.cin.trim() && CIN_ENTITY_TYPES.has(f.entity_type) && !CIN_RE.test(f.cin.trim().toUpperCase())) {
        e.cin = "Enter a valid CIN (e.g. U74999MH2020PTC123456).";
      } else if (f.cin.trim() && f.entity_type === "llp" && !LLPIN_RE.test(f.cin.trim().toUpperCase())) {
        e.cin = "LLPIN is 3 letters + 4 digits (e.g. AAB-1234).";
      } else if (f.cin.trim() && !CIN_ENTITY_TYPES.has(f.entity_type) && f.entity_type !== "llp" && f.cin.trim().length < 3) {
        e.cin = "Enter the registration number from your certificate.";
      }
    }

    // Cross-checks against CIN's own embedded data — only meaningful once the
    // CIN has already passed the plain format check above (no point cross-
    // checking a value that isn't even shaped like a CIN), and only for the
    // entity types that actually carry MCA's structured CIN (not LLPIN or a
    // generic Partnership/Trust filing number, which don't encode any of this).
    if (!e.cin && f.cin.trim() && CIN_ENTITY_TYPES.has(f.entity_type)) {
      const parsed = parseCin(f.cin);
      if (parsed) {
        const expectedClass = CIN_CLASS_BY_ENTITY[f.entity_type];
        if (expectedClass && parsed.classCode !== expectedClass) {
          e.cin = `This CIN's company class (${parsed.classCode}) doesn't match the selected entity type (expected ${expectedClass}).`;
        } else if (parsed.listing === "Listed" && CIN_CANNOT_BE_LISTED_ENTITY_TYPES.has(f.entity_type)) {
          e.cin = "This CIN's listing prefix (L) marks it as a listed company, which isn't possible for this entity type.";
        } else if (f.state && ROC_STATE_CODES[f.state] && parsed.stateCode !== ROC_STATE_CODES[f.state]) {
          e.cin = `This CIN's state code (${parsed.stateCode}) doesn't match the registered office state (${f.state}).`;
        } else if (f.date_of_incorporation && parsed.year !== f.date_of_incorporation.slice(0, 4)) {
          e.cin = `This CIN's registration year (${parsed.year}) doesn't match the Date of Incorporation (${f.date_of_incorporation.slice(0, 4)}).`;
        }
      }
    }

    if (f.pin_code.trim() && !isValidPin(f.pin_code.trim())) e.pin_code = "Enter a valid 6-digit Indian PIN code (can't start with 0).";

    if (f.iec.trim() && !PAN_RE.test(f.iec.trim().toUpperCase())) {
      e.iec = "IEC is PAN-based since 2018 — enter a valid 10-character PAN-format code.";
    } else if (f.iec.trim() && f.pan.trim() && f.iec.trim().toUpperCase() !== f.pan.trim().toUpperCase()) {
      e.iec = `IEC is PAN-based since 2018 and should match the company PAN (${f.pan.trim().toUpperCase()}).`;
    }
  } else {
    if (!f.country_of_registration.trim()) e.country_of_registration = "Country of registration is required for a foreign entity.";
    if (!f.registration_number.trim())     e.registration_number     = "Registration number is required for a foreign entity.";
    // EIN is a US IRS-issued tax ID — only required for US-registered
    // entities, same idea as CIN only applying to certain India entity types.
    if (f.country_of_registration === "US" && !f.ein.trim()) e.ein = "EIN is required for a US entity.";
  }

  if (!f.communication_address_same_as_registered) {
    if (!f.communication_address.trim()) e.communication_address = "Communication address is required when it differs from the registered office.";
    if (!f.communication_city.trim())    e.communication_city    = "Communication city is required when it differs from the registered office.";
    if (f.communication_pin_code.trim() && !isValidPin(f.communication_pin_code.trim()))
      e.communication_pin_code = "Enter a valid 6-digit Indian PIN code (can't start with 0).";
  }

  if (f.date_of_incorporation) {
    const today = new Date().toISOString().slice(0, 10);
    if (f.date_of_incorporation > today) {
      e.date_of_incorporation = "Date of Incorporation can't be in the future.";
    } else if (f.date_of_incorporation < MIN_INCORPORATION_DATE) {
      e.date_of_incorporation = "Enter a realistic Date of Incorporation.";
    }
  }

  if (f.website && !WEBSITE_RE.test(f.website.trim()))
    e.website = "Enter a full URL starting with http:// or https://.";
  if (f.official_phone && !PHONE_RE.test(f.official_phone)) e.official_phone = "Enter a valid phone number.";
  if (f.primary_email && !EMAIL_RE.test(f.primary_email))   e.primary_email  = "Enter a valid email address.";
  if (f.signatory_email && !EMAIL_RE.test(f.signatory_email)) e.signatory_email = "Enter a valid email address.";

  if (f.udyam_msme.trim() && !UDYAM_RE.test(f.udyam_msme.trim().toUpperCase()))
    e.udyam_msme = "Enter a valid Udyam number (e.g. UDYAM-TS-00-0000000).";
  if (f.epfo_code.trim() && !LOOSE_REGISTRATION_RE.test(f.epfo_code.trim().toUpperCase()))
    e.epfo_code = "EPFO code must be 30 characters or fewer, letters/digits/slashes/hyphens only.";
  if (f.esic_code.trim() && !ESIC_RE.test(f.esic_code.trim()))
    e.esic_code = "ESIC code must be exactly 17 digits.";
  if (f.professional_tax_reg.trim() && !LOOSE_REGISTRATION_RE.test(f.professional_tax_reg.trim().toUpperCase()))
    e.professional_tax_reg = "Must be 30 characters or fewer, letters/digits/slashes/hyphens only.";
  if (f.signatory_din_pan.trim()) {
    const v = f.signatory_din_pan.trim().toUpperCase();
    if (!DIN_RE.test(v) && !PAN_RE.test(v)) {
      e.signatory_din_pan = "Enter a valid DIN (8 digits) or PAN (10 characters) — the signatory is not always a director.";
    }
  }

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

// date_of_incorporation (and logo_url) are nullable on the backend — every
// other field is a plain CharField/TextField that always serializes as ""
// when unset, never null. Merging a raw API response straight into form
// state would let a null slip into a controlled <input value=>, which React
// warns about and half-renders as uncontrolled.
export function sanitizeCompanyResponse<T extends object>(raw: T): T {
  return Object.fromEntries(
    Object.entries(raw as Record<string, unknown>).map(([k, v]) => [k, v === null ? "" : v]),
  ) as T;
}

export function profileCompletionPercent(f: CompanyData): number {
  // CIN (or whatever this entity type's registration number is called, per
  // REGISTRATION_NUMBER_CONFIG) was previously left out of this calculation
  // entirely — a record could read "100% complete" while missing a required
  // registration number. Only counted when the field actually applies to
  // this entity type (Proprietorship/HUF genuinely have none, so it's
  // correctly excluded for those two, not silently 0%-weighted forever).
  const jurisdictionFields: (keyof CompanyData)[] = f.jurisdiction === "india"
    ? (REGISTRATION_NUMBER_CONFIG[f.entity_type] ? ["pan", "tan", "cin"] : ["pan", "tan"])
    : ["country_of_registration", "registration_number"];
  const fields = [...COMPLETION_FIELDS, ...jurisdictionFields];
  const filled = fields.filter(k => String(f[k] ?? "").trim().length > 0).length;
  return Math.round((filled / fields.length) * 100);
}
