// Before the final "Hire", the wizard re-saves the form and gets the draft the SERVER now holds. This compares the two for the
// fields hiring depends on, so a value that is on screen but never reached the server is reported by name instead of being
// discovered as a vague refusal after the hire request.

const WATCHED_FIELDS: ReadonlyArray<readonly [string, string]> = [
  ["first_name", "First name"], ["last_name", "Last name"], ["email", "Personal email"], ["branch", "Company code"],
  ["pan_number", "PAN"], ["aadhaar_number", "Aadhaar"], ["account_holder_name", "Account holder name"],
  ["account_number", "Account number"], ["ifsc_code", "IFSC code"],
];

const asText = (value: unknown): string => (typeof value === "string" ? value.trim() : value == null ? "" : String(value).trim());

/** Labels of the watched fields that have a value on screen but a different (usually empty) value on the server. */
export function fieldsTheServerDidNotKeep(sent: Record<string, unknown>, held: Record<string, unknown> | null | undefined): string[] {
  const saved = held ?? {};
  return WATCHED_FIELDS
    .filter(([key]) => asText(sent[key]) !== "" && asText(saved[key]) === "")
    .map(([, label]) => label);
}
