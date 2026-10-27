"use client";

import { PROFILE_SECTIONS } from "../../_data";

export default function ProfileSidebar({
  active,
  onChange,
}: {
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <nav
      className="rounded-xl border p-1 sticky top-4 self-start"
      style={{ background: "var(--surface)", borderColor: "var(--outline-v)" }}
    >
      <ul className="flex flex-col gap-0.5">
        {PROFILE_SECTIONS.map((s) => {
          const isActive = active === s.id;
          return (
            <li key={s.id}>
              <button
                onClick={() => onChange(s.id)}
                suppressHydrationWarning
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium text-left whitespace-nowrap transition-all"
                style={{
                  background: isActive ? "var(--bg-mid)" : "transparent",
                  color: isActive ? "var(--primary)" : "var(--on-variant)",
                  borderLeft: isActive ? "3px solid var(--primary)" : "3px solid transparent",
                }}
              >
                <i
                  className={`ti ${s.icon} text-[15px] flex-shrink-0`}
                  style={{ color: isActive ? "var(--primary)" : "var(--outline)" }}
                />
                {s.label}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
