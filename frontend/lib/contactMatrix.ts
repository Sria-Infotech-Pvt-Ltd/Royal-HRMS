// Company Contact Matrix — grouping for display and the add/edit form check.
// Contacts are entered by HR; nothing is pre-filled.

export interface CompanyContact {
  id: number;
  name: string;
  designation: string;
  department: string;
  email: string;
  phone: string;
  purpose: string;
  escalation_level: number;
  branch: number | null;
  branch_name: string;
  display_order: number;
}

export type ContactForm = Omit<CompanyContact, "id" | "branch_name">;

export const EMPTY_CONTACT: ContactForm = {
  name: "", designation: "", department: "", email: "", phone: "", purpose: "",
  escalation_level: 1, branch: null, display_order: 0,
};

/** Contacts grouped by escalation level, lowest (first point of contact) first. */
export function groupByLevel(contacts: CompanyContact[]): { level: number; contacts: CompanyContact[] }[] {
  const byLevel = new Map<number, CompanyContact[]>();
  for (const c of contacts) byLevel.set(c.escalation_level, [...(byLevel.get(c.escalation_level) ?? []), c]);
  return [...byLevel.entries()].sort(([a], [b]) => a - b).map(([level, list]) => ({
    level,
    contacts: [...list].sort((x, y) => x.display_order - y.display_order || x.name.localeCompare(y.name)),
  }));
}

export function levelLabel(level: number): string {
  return level <= 1 ? "First point of contact" : `Escalation level ${level}`;
}

export function contactFormError(form: ContactForm): string | null {
  if (!form.name.trim()) return "Name is required.";
  if (!form.email.trim() && !form.phone.trim()) return "Enter an email or a phone number.";
  if (form.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return "Enter a valid email address.";
  if (form.escalation_level < 1) return "Escalation level starts at 1.";
  return null;
}
