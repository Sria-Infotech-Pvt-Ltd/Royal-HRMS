"use client";

import type { ReactNode } from "react";
import { useRouter } from "next/navigation";

interface Props {
  href: string;
  /** Spoken name for the whole card, e.g. "Open employees". */
  label: string;
  children: ReactNode;
}

// Makes a whole dashboard card a link: click or Enter/Space opens the page it summarises. A div (not an <a> or <button>)
// because the cards hold their own headings, charts and, sometimes, buttons.
export default function LinkCard({ href, label, children }: Props) {
  const router = useRouter();
  const open = () => router.push(href);
  return (
    <div
      role="link"
      tabIndex={0}
      aria-label={label}
      className="wf-linkcard"
      onClick={open}
      onKeyDown={event => {
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      }}
    >
      {children}
    </div>
  );
}
