// Shapes and fixed lists for the Family & nomination step. Re-exported from FamilyNominationStep.tsx, which is where the Hire wizard,
// the HR-assisted onboarding page and Edit Record already import FamilyEntry and NomineeEntry from.

export interface FamilyEntry {
  id: string;
  name: string;
  relationship: string;
  date_of_birth: string;
  gender: string;
  blood_group: string;
  is_dependent: boolean;
}

export interface NomineeEntry {
  id: string;
  family_member: string; // FamilyEntry.id; may be a temp- id until saved
  scheme: string;
  share_percentage: string;
}

export const RELATIONSHIPS = ["father", "mother", "spouse", "child", "sibling"] as const;
export const RELATIONSHIP_LABELS: Record<string, string> = {
  father: "Father", mother: "Mother", spouse: "Spouse", child: "Child", sibling: "Sibling",
};
export const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

/** The three nominee groups the backend knows. "both" is its own group here, exactly as the totals and the Review check count it. */
export const SCHEMES: { value: string; label: string; hint: string }[] = [
  { value: "epf_eps",  label: "EPF + EPS", hint: "Provident fund and pension" },
  { value: "gratuity", label: "Gratuity",  hint: "Gratuity payout" },
  { value: "both",     label: "Both",      hint: "A separate group of nominees" },
];

export const MINOR_AGE_YEARS = 18;
