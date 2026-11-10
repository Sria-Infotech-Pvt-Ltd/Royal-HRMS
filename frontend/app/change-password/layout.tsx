import type { ReactNode } from "react";

// Change-password uses the new design's colours (see app/new-ui-bridge.css), in light and dark.
export default function ChangePasswordLayout({ children }: { children: ReactNode }) {
  return <div className="new-ui">{children}</div>;
}
