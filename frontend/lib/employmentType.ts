// Employment types the backend accepts (User.EMPLOYMENT_TYPE_CHOICES), and tolerant matching of stored values.
export const EMPLOYMENT_TYPES = ["Permanent", "Contract", "Freelancer", "Consultant", "Part-Time", "Temporary", "Intern"];

const ALIASES: Record<string, string> = {
  fulltime: "Permanent", regular: "Permanent", employee: "Permanent",
  contractor: "Contract", contractual: "Contract", fixedterm: "Contract",
  freelance: "Freelancer", consulting: "Consultant", temp: "Temporary", internship: "Intern", trainee: "Intern",
};

const squash = (raw: string): string => raw.toLowerCase().replace(/[^a-z]/g, "");

/** Map a stored value ("full time", "PERMANENT") to its dropdown option; unknown values come back unchanged. */
export function matchEmploymentType(raw: string): string {
  const key = squash(raw);
  if (!key) return "";
  return EMPLOYMENT_TYPES.find(type => squash(type) === key) ?? ALIASES[key] ?? raw;
}
