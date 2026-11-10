import type { ReactNode } from "react";

// Onboarding screens use the new design's colours (see app/new-ui-bridge.css), in light and dark.
export default function OnboardingLayout({ children }: { children: ReactNode }) {
  return <div className="new-ui">{children}</div>;
}
