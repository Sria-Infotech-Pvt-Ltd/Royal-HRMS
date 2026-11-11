import type { ReactNode } from "react";

// The activation screen uses the new design's colours (see app/new-ui-bridge.css), in light and dark.
export default function ActivateLayout({ children }: { children: ReactNode }) {
  return <div className="new-ui">{children}</div>;
}
