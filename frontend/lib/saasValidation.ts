// Field rules for the Platform Admin SaaS & Subscriptions forms. They mirror
// backend/apps/tenants/validators.py + serializers_saas.py (the server always
// re-checks). Each check returns an error message, or null when the value is fine.

export type Errors = Record<string, string>;

export const MAX_EMPLOYEES = 100000;
export const MAX_AMOUNT = 9999999999.99;
const EARLIEST = "2000-01-01";

const PLAN_CODE_RE = /^[a-z][a-z0-9-]{1,39}$/;
const COMPANY_CODE_RE = /^[A-Z][A-Z0-9]{2,19}$/;
const RESERVED_CODES = new Set(["PUBLIC", "ADMIN", "PLATFORM", "ROYAL", "ROYALHRMS", "TEST", "SYSTEM", "API", "WWW"]);
const PERSON_NAME_RE = /^\p{L}[\p{L} .'-]*$/u;
const NAME_CHARS_RE = /^[\p{L}\p{N}_ &.,'()/+-]+$/u;
const PHONE_RE = /^[0-9+\-\s()]{7,20}$/;
const GSTIN_RE = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const REFERENCE_RE = /^[A-Za-z0-9 ./_#:-]+$/;
const DECIMAL_RE = /^\d+(\.\d{1,2})?$/;

export const required = (v: string, what = "This field") => (v.trim() ? null : `${what} is required.`);

export function personName(v: string): string | null {
  const s = v.trim();
  return !s || PERSON_NAME_RE.test(s) ? null : "Use letters only (spaces, . ' - allowed).";
}

export function businessName(v: string, what = "Name"): string | null {
  const s = v.trim();
  if (!s) return `${what} is required.`;
  return NAME_CHARS_RE.test(s) && /\p{L}/u.test(s) ? null : `${what} must contain letters (digits and & . , ' ( ) / + - allowed).`;
}

export const planCode = (v: string) =>
  PLAN_CODE_RE.test(v.trim()) ? null : "2–40 lowercase letters, digits or hyphens, starting with a letter (e.g. growth).";

export function companyCode(v: string): string | null {
  const s = v.trim().toUpperCase();
  if (!s) return "Company code is required.";
  if (!COMPANY_CODE_RE.test(s)) return "3–20 letters or digits, starting with a letter.";
  return RESERVED_CODES.has(s) ? "This company code is reserved. Choose another." : null;
}

export const email = (v: string, isRequired = true) =>
  !v.trim() ? (isRequired ? "Email is required." : null) : EMAIL_RE.test(v.trim()) ? null : "Enter a valid email address.";

export function phone(v: string): string | null {
  const s = v.trim();
  if (!s) return null;
  return PHONE_RE.test(s) && s.replace(/\D/g, "").length >= 7 ? null : "Enter a valid phone number (digits, spaces, + - ( ) only).";
}

export const gstin = (v: string) =>
  !v.trim() || GSTIN_RE.test(v.trim().toUpperCase()) ? null : "Enter a valid 15-character GSTIN (e.g. 22AAAAA0000A1Z5).";

/** Money / percentage: digits with at most 2 decimals, within [min, max]. */
export function decimal(v: string, { min = 0, max = MAX_AMOUNT, minExclusive = false, isRequired = true, what = "Amount" } = {}): string | null {
  const s = v.trim();
  if (!s) return isRequired ? `${what} is required.` : null;
  if (/^-\d/.test(s)) return `${what} cannot be negative.`;
  if (!DECIMAL_RE.test(s)) return `${what} must be a number with up to 2 decimals.`;
  const n = Number(s);
  if (minExclusive ? n <= min : n < min) return minExclusive ? `${what} must be more than ${min}.` : `${what} cannot be less than ${min}.`;
  return n > max ? `${what} cannot be more than ${max.toLocaleString("en-IN")}.` : null;
}

/** Whole number within [min, max]; blank allowed unless required. */
export function wholeNumber(v: string, { min = 1, max = MAX_EMPLOYEES, isRequired = false, what = "Value" } = {}): string | null {
  const s = v.trim();
  if (!s) return isRequired ? `${what} is required.` : null;
  if (!/^\d+$/.test(s)) return `${what} must be a whole number.`;
  const n = Number(s);
  return n < min || n > max ? `${what} must be between ${min} and ${max.toLocaleString("en-IN")}.` : null;
}

const todayISO = () => new Date().toISOString().slice(0, 10);
const plusYears = (years: number) => { const d = new Date(); d.setFullYear(d.getFullYear() + years); return d.toISOString().slice(0, 10); };

/** YYYY-MM-DD that is a real calendar date within a sensible range. */
export function date(v: string, { isRequired = true, notFuture = false, what = "Date" } = {}): string | null {
  if (!v) return isRequired ? `${what} is required.` : null;
  const d = new Date(`${v}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v) || Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== v) return `Enter a valid ${what.toLowerCase()}.`;
  if (v < EARLIEST) return `${what} must be after 2000.`;
  if (notFuture && v > todayISO()) return `${what} cannot be in the future.`;
  return v > plusYears(5) ? `${what} is too far in the future.` : null;
}

export const reference = (v: string) =>
  !v.trim() || REFERENCE_RE.test(v.trim()) ? null : "Letters, digits, spaces and . / _ # : - only.";

export const maxLength = (v: string, n: number) => (v.length > n ? `Keep this under ${n} characters.` : null);

/** Keep only the failing checks. */
export function collect(checks: Record<string, string | null>): Errors {
  return Object.fromEntries(Object.entries(checks).filter(([, m]) => m)) as Errors;
}

/** Field errors from an API error response (`data` holds DRF serializer errors; nested
 *  objects such as new_company are flattened to "new_company.company_code"). */
export function apiFieldErrors(err: unknown): Errors {
  const data = (err as { response?: { data?: { data?: unknown } } })?.response?.data?.data;
  const out: Errors = {};
  const walk = (obj: unknown, prefix: string) => {
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return;
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      const key = prefix ? `${prefix}.${k}` : k;
      if (Array.isArray(v) && typeof v[0] === "string") out[key] = v[0];
      else if (typeof v === "string") out[key] = v;
      else walk(v, key);
    }
  };
  walk(data, "");
  return out;
}
