// The one mobile rule, same as the server's (apps/accounts/validators.validate_mobile_number): a 10-digit Indian mobile starting
// 6-9, with an optional +91 / 91 prefix and spaces or dashes. Used by the hire form, Edit full record and Edit my details.

export const MOBILE_ERROR = "Enter a valid 10-digit Indian mobile number (it must start with 6, 7, 8 or 9).";

const MOBILE_PATTERN = /^(?:\+?91)?([6-9]\d{9})$/;

/** The 10 digits, or null when the text is not a valid Indian mobile number. */
export function normaliseMobile(value: string): string | null {
  const compact = value.replace(/[\s\-()./]/g, "");
  const match = MOBILE_PATTERN.exec(compact);
  return match ? match[1] : null;
}

/** An error message for a typed mobile, or null when it is valid. Blank is valid (use a required check where it is mandatory). */
export function mobileError(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  return normaliseMobile(trimmed) ? null : MOBILE_ERROR;
}
