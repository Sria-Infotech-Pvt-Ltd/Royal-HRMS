// The Section / Field choices of the "Request profile correction" modal. The same lists live on the server in
// backend/apps/hrms/profile_correction_fields.py, which rejects any pair not listed here: change both together.

export const OTHER_SECTION = "Other";
export const OTHER_FIELD = "Other (describe in the reason)";

export interface CorrectionSection {
  value: string;
  fields: string[];
}

export const CORRECTION_SECTIONS: CorrectionSection[] = [
  {
    value: "Personal details",
    fields: [
      "Full name", "Salutation", "Middle name", "Display name", "Date of birth", "Place of birth", "Gender", "Marital status",
      "Nationality", "Father's name", "Mother's name", "Blood group", "Languages known",
      // An employment date, but it is the field people most often get wrong at onboarding, and there is no Employment section.
      "Date of joining",
    ],
  },
  {
    value: "Contact & address",
    fields: [
      "Mobile number", "Personal email",
      "Current address", "Current village / town", "Current district", "Current state", "Current PIN code",
      "Permanent address", "Permanent village / town", "Permanent district", "Permanent state", "Permanent PIN code",
    ],
  },
  {
    value: "Emergency contact",
    fields: ["Emergency contact name", "Emergency contact relationship", "Emergency contact phone", "Emergency contact email"],
  },
  {
    value: "Bank details",
    fields: ["Bank name", "Branch name", "Account holder name", "Account type", "Account number", "IFSC code"],
  },
  {
    value: "Family & nomination",
    fields: [
      "Family member name", "Family member relationship", "Family member date of birth", "Family member gender",
      "Family member blood group", "Dependent status", "Nominee and share percentage", "Add or remove a family member",
    ],
  },
  { value: OTHER_SECTION, fields: [OTHER_FIELD] },
];

export function fieldsForSection(section: string): string[] {
  return CORRECTION_SECTIONS.find(entry => entry.value === section)?.fields ?? [];
}
