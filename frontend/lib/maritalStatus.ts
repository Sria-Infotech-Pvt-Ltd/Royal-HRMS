// The five marital statuses the backend accepts (EmployeeProfile.MARITAL_CHOICES), with the label people should see.

export interface MaritalStatusOption {
  value: string;
  label: string;
}

export const MARITAL_STATUS_OPTIONS: MaritalStatusOption[] = [
  { value: "single", label: "Single" },
  { value: "married", label: "Married" },
  { value: "divorced", label: "Divorced" },
  { value: "widowed", label: "Widowed" },
  { value: "separated", label: "Separated" },
];

/** "single" -> "Single". Never shows the raw stored value; an unknown value is title-cased, blank becomes "—". */
export function maritalStatusLabel(value: string | null | undefined): string {
  const stored = (value ?? "").trim().toLowerCase();
  if (!stored) return "—";
  const known = MARITAL_STATUS_OPTIONS.find(option => option.value === stored);
  return known ? known.label : stored.charAt(0).toUpperCase() + stored.slice(1);
}
