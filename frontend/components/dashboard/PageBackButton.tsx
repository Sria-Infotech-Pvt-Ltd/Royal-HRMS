"use client";

import { usePathname, useRouter } from "next/navigation";
import { backFallbackPath, shouldShowBackButton } from "@/lib/pageBack";

/** A Back button at the top of a dashboard page. Goes to the page you came from; if this page was opened directly, to the page above it. */
export default function PageBackButton() {
  const router = useRouter();
  const pathname = usePathname();
  if (!shouldShowBackButton(pathname)) return null;

  function goBack() {
    if (window.history.length > 1) router.back();
    else router.push(backFallbackPath(pathname));
  }

  return (
    <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
      <button type="button" className="btn btn-ghost btn-sm" onClick={goBack} aria-label="Go back">
        <i className="ti ti-arrow-left" /> Back
      </button>
    </div>
  );
}
