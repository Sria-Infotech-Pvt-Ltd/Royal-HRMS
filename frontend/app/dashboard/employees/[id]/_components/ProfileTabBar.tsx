"use client";

import { PROFILE_TABS } from "../../_data";

export default function ProfileTabBar({
  active,
  onChange,
}: {
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div
      className="rounded-xl border mb-4 overflow-x-auto"
      style={{ background: "var(--surface)", borderColor: "var(--outline-v)" }}
    >
      <div className="flex items-center px-2 py-1.5 gap-0.5 min-w-max">
        {PROFILE_TABS.map((t) => {
          const isActive = active === t.id;
          return (
            <button
              key={t.id}
              onClick={() => onChange(t.id)}
              suppressHydrationWarning
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium whitespace-nowrap transition-all"
              style={{
                background: isActive ? "var(--primary)" : "transparent",
                color: isActive ? "#fff" : "var(--on-variant)",
              }}
            >
              <i className={`ti ${t.icon} text-[14px]`} />
              {t.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
