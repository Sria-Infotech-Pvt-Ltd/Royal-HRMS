// Values the HR approval screen may send along with "approve".
//
// The approval payload always returns the PAN MASKED (for example "ABCDE••••F"), because HR must not see it without the audited reveal.
// Checking or re-sending that masked text is wrong: it can never match the PAN format, and the screen then refused to approve anyone
// who had entered a PAN. The server keeps the stored PAN when none is sent, so a masked value is simply left out.

export const PAN_RE = /^[A-Za-z]{5}[0-9]{4}[A-Za-z]$/;

/** The PAN to send with an approval, or "" when only the masked form is known (the stored PAN is then left untouched). */
export function usablePan(raw: string | null | undefined): string {
  const value = (raw ?? "").trim();
  return PAN_RE.test(value) ? value.toUpperCase() : "";
}

/** Message for a value that really is wrong, or null. A masked PAN is not an error. */
export function approvalFieldError(uan: string | null | undefined, rawPan: string | null | undefined): string | null {
  const uanValue = (uan ?? "").trim();
  if (uanValue && uanValue.length !== 12) return "UAN must be exactly 12 digits, or leave it blank.";
  const panValue = (rawPan ?? "").trim();
  const isMasked = panValue.includes("•") || panValue.includes("*");
  if (panValue && !isMasked && !PAN_RE.test(panValue)) return "Enter a valid PAN (e.g. ABCDE1234F), or leave it blank.";
  return null;
}
