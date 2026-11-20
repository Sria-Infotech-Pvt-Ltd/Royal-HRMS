import InfoPage, { type InfoSection } from "@/components/dashboard/InfoPage";
import InfoHighlights, { type InfoHighlight } from "@/components/dashboard/InfoHighlights";
import InfoTable, { type InfoTableData } from "@/components/dashboard/InfoTable";

// What AIRA keeps, for how long, and who can see it. Every line here describes something the system really does (the retention and
// erasure wording is the one each employee record already shows under "Consent & Retention"); change this page when that behaviour changes.
// Do not add a retention period, a certification or a legal claim that the system does not itself state or enforce.
const HIGHLIGHTS: InfoHighlight[] = [
  { value: "8 years", label: "an employee record is kept after the person leaves (Income Tax and EPF)" },
  { value: "On exit", label: "a person's stored Face ID registration is deleted" },
  { value: "30 days", label: "bulk employee import details are kept after the import finishes" },
  { value: "Audit log", label: "important actions are recorded and cannot be edited from the screens" },
];

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
      "To see, correct or ask to erase your information, raise an HR help request from the HR help tab on your workspace.",
      "Corrections to your own profile go through HR so the change is recorded and approved.",
    ],
  },
];

const RETENTION_SCHEDULE: InfoTableData = {
  icon: "ti-calendar-time", title: "Retention schedule",
  intro: "How each kind of information is treated, in one place.",
  columns: ["Information", "How long", "What happens"],
  rows: [
    ["Employee record of someone who has left", "8 years", "Kept for tax and provident fund record-keeping. Statutory records are not removed earlier."],
    ["Employee record of a deactivated employee", "While kept for compliance", "Marked inactive, not deleted."],
    ["Non-statutory profile fields", "Until erasure is requested", "Can be erased on request through HR."],
    ["Face ID registration", "Until the person leaves", "Deleted on exit. A record that a check took place stays for audit, with no biometric data."],
    ["Bulk employee import details", "30 days after the import finishes", "The rows and any errors are deleted."],
    ["Audit log entries", "Kept for audit", "Cannot be edited from the screens."],
  ],
};

const ACCESS_BY_ROLE: InfoTableData = {
  icon: "ti-users", title: "Who sees what",
  intro: "Access follows roles and permissions. The server enforces it, not just the screens.",
  columns: ["Role", "What they can see"],
  rows: [
    ["Employee", "Their own information and their own requests."],
    ["Reporting manager", "Their own team, not everyone."],
    ["HR roles", "Employee information their role allows, limited to their own branch where one is set."],
    ["System administrators", "All branches, as their full-access role allows."],
  ],
};

export default function PrivacyPage() {
  return (
    <InfoPage
      icon="ti-info-circle"
      title="Privacy & retention"
      subtitle="What AIRA keeps about you, for how long, and who can see it."
      lead={<InfoHighlights items={HIGHLIGHTS} label="Key facts" />}
      sections={SECTIONS}
      extra={<><InfoTable {...RETENTION_SCHEDULE} /><InfoTable {...ACCESS_BY_ROLE} /></>}
      footnote="This page describes how the system works. Your company's own policy and the law apply. For the full policy, ask HR."
    />
  );
}
