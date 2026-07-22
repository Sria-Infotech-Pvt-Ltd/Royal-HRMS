// Shared client-side validation for candidate name / position / phone / interview date.
// Mirrors the rules enforced server-side in backend/apps/recruitment/serializers.py
// (_NAME_RE, _POSITION_RE, _PHONE_RE, validate_interview_date) so Add/Edit candidate
// forms give the same feedback before hitting the API.

export const NAME_RE     = /^[A-Za-z][A-Za-z .'-]*$/;
export const POSITION_RE = /^[A-Za-z][A-Za-z .&/-]*$/;
export const PHONE_RE    = /^\+?[0-9]{10,15}$/;

export function sanitizeName(value: string): string {
  return value.replace(/[^A-Za-z .'-]/g, "");
}

export function sanitizePosition(value: string): string {
  return value.replace(/[^A-Za-z .&/-]/g, "");
}

export function sanitizePhone(value: string): string {
  let digitsAndPlus = value.replace(/[^\d+]/g, "");
  if (digitsAndPlus.includes("+")) {
    digitsAndPlus = "+" + digitsAndPlus.replace(/\+/g, "");
  }
  const maxLength = digitsAndPlus.startsWith("+") ? 16 : 15;
  return digitsAndPlus.slice(0, maxLength);
}

export function todayDateString(): string {
  return new Date().toISOString().slice(0, 10);
}
