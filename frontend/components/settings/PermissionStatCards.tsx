"use client";

import StatCardGrid from "./StatCardGrid";

interface Props {
  granted: number;
  total: number;
  sensitive: number;
  modulesFullyOn: number;
  moduleCount: number;
  changed: number;
}

/** Four numbers above the baseline matrix: how much is switched on, how many modules are fully on, sensitive access, unsaved edits. */
export default function PermissionStatCards({ granted, total, sensitive, modulesFullyOn, moduleCount, changed }: Props) {
  const percent = total === 0 ? 0 : Math.round((granted / total) * 100);
  return (
    <StatCardGrid
      cards={[
        { icon: "ti-shield-check", tone: "var(--primary)", label: "Enabled for everyone", value: `${granted} of ${total}`, note: `${percent}% of all permissions` },
        { icon: "ti-layout-grid", tone: "var(--success)", label: "Modules fully on", value: `${modulesFullyOn} of ${moduleCount}`, note: "Every permission in the module" },
        {
          icon: "ti-alert-triangle", tone: "var(--warn)", label: "Sensitive switched on", value: String(sensitive),
          note: sensitive === 0 ? "No sensitive access for everyone" : "Given to every employee: review",
        },
        {
          icon: "ti-pencil", tone: changed === 0 ? "var(--on-variant)" : "var(--primary)", label: "Unsaved changes", value: String(changed),
          note: changed === 0 ? "Everything is saved" : "Save to apply them",
        },
      ]}
    />
  );
}
