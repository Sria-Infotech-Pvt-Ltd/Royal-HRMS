import InfoPage, { type InfoSection } from "@/components/dashboard/InfoPage";

// What AIRA keeps, for how long, and who can see it. Every line here describes something the system really does (the retention and
// erasure wording is the one each employee record already shows under "Consent & Retention"); change this page when that behaviour changes.
const SECTIONS: InfoSection[] = [
  {
    icon: "ti-database", title: "What is kept, and why",
    points: [
      "Employee records are kept for payroll, statutory filing, benefits and workplace administration.",
      "Attendance, leave, expense, work-from-home and similar requests are kept with who decided them and when.",
      "Face ID, where you registered it, is used to check it is you when you punch in or out.",
    ],
  },
  {
    icon: "ti-clock-hour-4", title: "How long it is kept",
    points: [
      "After someone leaves, their record is kept for 8 years, for Income Tax and EPF record-keeping.",
      "Deactivating an employee does not delete the record: it is marked inactive and kept for statutory compliance.",
      "Non-statutory fields can be erased on request. Statutory records cannot be deleted early.",
      "When someone leaves, their stored Face ID registration is deleted. A record that a check happened is kept for audit, without the biometric data.",
      "Details of a bulk employee import (the rows and any errors) are deleted 30 days after the import finishes.",
    ],
  },
  {
    icon: "ti-eye-check", title: "Who can see it",
    points: [
      "Access follows roles and permissions: people see only what their role allows, and HR roles are limited to their own branch where that is set.",
      "A reporting manager sees their own team, not everyone.",
      "Important actions are written to an audit log (who did what, and when) that cannot be edited from the screens.",
    ],
  },
  {
    icon: "ti-user-question", title: "Your questions and requests",
    points: [
      "To see, correct or ask to erase your information, raise an HR help request from the Support link or the HR help tab on your workspace.",
      "Corrections to your own profile go through HR so the change is recorded and approved.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <InfoPage
      icon="ti-info-circle"
      title="Privacy & retention"
      subtitle="What AIRA keeps about you, for how long, and who can see it."
      sections={SECTIONS}
      footnote="This page describes how the system works. Your company's own policy and the law apply. For the full policy, ask HR."
    />
  );
}
