import InfoPage, { type InfoSection } from "@/components/dashboard/InfoPage";

// How AIRA protects sign-in and access. Every number here comes from the backend settings (config/settings.py, accounts/utils.py);
// change this page when those settings change.
const SECTIONS: InfoSection[] = [
  {
    icon: "ti-key", title: "Signing in",
    points: [
      "Passwords must be long enough, not a common password, not only numbers, and not too similar to your name or email.",
      "After 5 wrong passwords your account is locked for 30 minutes.",
      "Codes sent by email (for example to reset a password) work for 10 minutes, allow 5 tries, and a new one can be asked for after 1 minute.",
      "The link in an onboarding invitation works once, for 72 hours. If it expires, HR can send a new one, and the old link then stops working.",
    ],
  },
  {
    icon: "ti-device-laptop", title: "Your session",
    points: [
      "Your sign-in is kept in a protected cookie that the page's scripts cannot read.",
      "You stay signed in for up to 7 days. The short-lived part of your sign-in lasts 15 minutes and is renewed automatically while you are signed in.",
      "Sign out on a shared computer. Signing out ends the session.",
    ],
  },
  {
    icon: "ti-shield-lock", title: "Who can do what",
    points: [
      "Every action is checked on the server against your role and permissions, not only on the screen.",
      "You cannot approve your own leave or expense requests.",
      "Where Face ID is set up, it is checked when you punch in or out.",
    ],
  },
  {
    icon: "ti-history", title: "Records and audit",
    points: [
      "Important actions (sign-ins, changes in Settings, approvals, employee changes) are recorded with who did them and when.",
      "People with the right permission can review these in the Audit Log.",
      "Emails the system sends are logged, with whether they were delivered.",
    ],
  },
  {
    icon: "ti-alert-triangle", title: "If something looks wrong",
    points: [
      "If you did not request a password reset or invitation email, do not click the link and tell HR.",
      "If you think someone used your account, change your password and raise an HR help request straight away.",
    ],
  },
];

export default function SecurityPage() {
  return (
    <InfoPage
      icon="ti-info-circle"
      title="Security"
      subtitle="How AIRA protects your sign-in and your information."
      sections={SECTIONS}
      footnote="This page describes how the system works. It is not a certification or a guarantee. To report a concern, contact HR."
    />
  );
}
