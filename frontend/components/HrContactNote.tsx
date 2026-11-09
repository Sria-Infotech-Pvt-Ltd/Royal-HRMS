import type { HrContact } from "@/types/onboardingLink";

interface HrContactNoteProps {
  contact: HrContact | null;
}

/** "Questions? Contact <HR name> at <email>" — rendered only when an HR contact is known. */
export default function HrContactNote({ contact }: HrContactNoteProps) {
  if (!contact) return null;
  return (
    <p style={{ fontSize: ".82rem", color: "var(--on-variant)", marginBottom: "1rem" }}>
      Questions? Contact {contact.name} at <a href={`mailto:${contact.email}`}>{contact.email}</a>.
    </p>
  );
}
