// One place that turns a failed API call into something a form can show: a readable message, plus one message per field.
//
// The backend answers failures in the envelope { message, data } where `message` is the first error ("gratuity_amount:
// Gratuity cannot be negative.") and `data` holds every field's errors. Plain DRF responses ({ detail }, { non_field_errors },
// { field: [messages] }) are understood too. Field keys the person never typed ("gratuity_amount") become labels ("Gratuity").

export interface ParsedApiError {
  /** The message for a toast or a form-level alert; field keys already replaced by labels. */
  message: string;
  /** One message per field key (the server's key, e.g. "phone"), for showing beside the input. */
  fieldErrors: Record<string, string>;
  status: number | null;
}

/** Labels for keys that read badly once humanised. Anything not listed becomes "Sentence case". */
export const FIELD_LABELS: Record<string, string> = {
  phone: "Mobile number",
  uan_number: "UAN",
  esi_number: "ESI number",
  email: "Email",
  emergency_phone: "Emergency contact phone",
  emergency_email: "Emergency contact email",
  current_pin_code: "Current PIN code",
  permanent_pin_code: "Permanent PIN code",
  file: "Document",
  document: "Supporting document",
  document_type: "Document type",
  start_date: "Start date",
  end_date: "End date",
  gratuity_amount: "Gratuity",
  statutory_bonus_amount: "Statutory bonus",
  reimbursements_amount: "Pending reimbursements",
  advances_recovery_amount: "Advances recovery",
  tds_amount: "TDS",
  other_adjustment_amount: "Other adjustment",
  other_adjustment_note: "Other adjustment note",
  is_recovery: "Recovery",
};

// Keys of the envelope itself, never field names.
const RESERVED_KEYS = new Set(["message", "detail", "status", "data", "non_field_errors", "error"]);
const PREFIX_PATTERN = /^([a-z][a-z0-9_]*): ([\s\S]+)$/;

function humanise(key: string): string {
  const spaced = key.replace(/_/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function labelFor(key: string, labels?: Record<string, string>): string {
  return labels?.[key] ?? FIELD_LABELS[key] ?? humanise(key);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** First readable string inside a DRF error value: "text", ["text"], or nested { child: ["text"] }. */
function firstText(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    for (const item of value) {
      const text = firstText(item);
      if (text) return text;
    }
    return null;
  }
  if (isRecord(value)) {
    for (const child of Object.values(value)) {
      const text = firstText(child);
      if (text) return text;
    }
  }
  return null;
}

/** "Gratuity: Gratuity cannot be negative." reads as a stutter, so the label is added only when the text lacks it. */
function withLabel(label: string, text: string): string {
  return text.toLowerCase().includes(label.toLowerCase()) ? text : `${label}: ${text}`;
}

function collectFieldErrors(source: unknown): Record<string, string> {
  const fieldErrors: Record<string, string> = {};
  if (!isRecord(source)) return fieldErrors;
  for (const [key, value] of Object.entries(source)) {
    if (RESERVED_KEYS.has(key)) continue;
    const text = firstText(value);
    if (text) fieldErrors[key] = text;
  }
  return fieldErrors;
}

export function parseApiError(err: unknown, fallback: string, labels?: Record<string, string>): ParsedApiError {
  const failure = isRecord(err) ? err : {};
  const response = isRecord(failure.response) ? failure.response : {};
  const body = isRecord(response.data) ? response.data : {};
  const statusValue = failure.status ?? response.status;
  const status = typeof statusValue === "number" ? statusValue : null;

  // The envelope's `data` first; plain DRF puts the field errors on the body itself.
  let fieldErrors = collectFieldErrors(body.data);
  if (Object.keys(fieldErrors).length === 0) fieldErrors = collectFieldErrors(body);

  const rawMessage =
    firstText(body.message) ?? firstText(body.detail) ?? firstText(body.non_field_errors) ??
    firstText(failure.message) ?? null;

  // A message the server prefixed with its field key ("phone: ...") still tells us which field it is about.
  const prefixed = rawMessage ? PREFIX_PATTERN.exec(rawMessage) : null;
  if (prefixed && Object.keys(fieldErrors).length === 0) fieldErrors[prefixed[1]] = prefixed[2];

  let message = rawMessage ?? fallback;
  if (prefixed) message = withLabel(labelFor(prefixed[1], labels), prefixed[2]);
  else if (!rawMessage && Object.keys(fieldErrors).length > 0) {
    const [key, text] = Object.entries(fieldErrors)[0];
    message = withLabel(labelFor(key, labels), text);
  }
  return { message, fieldErrors, status };
}
