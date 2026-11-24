"use client";

import { useT } from "@/hooks/useI18n";
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
  const t = useT();
  const percent = total === 0 ? 0 : Math.round((granted / total) * 100);
  return (
    <StatCardGrid
      cards={[
        { icon: "ti-shield-check", tone: "var(--primary)", label: t("Enabled for everyone"), value: t("{granted} of {total}", { granted, total }), note: t("{percent}% of all permissions", { percent }) },
        { icon: "ti-layout-grid", tone: "var(--success)", label: t("Modules fully on"), value: t("{granted} of {total}", { granted: modulesFullyOn, total: moduleCount }), note: t("Every permission in the module") },
        {
          icon: "ti-alert-triangle", tone: "var(--warn)", label: t("Sensitive switched on"), value: String(sensitive),
          note: sensitive === 0 ? t("No sensitive access for everyone") : t("Given to every employee: review"),
        },
        {
          icon: "ti-pencil", tone: changed === 0 ? "var(--on-variant)" : "var(--primary)", label: t("Unsaved changes"), value: String(changed),
          note: changed === 0 ? t("Everything is saved") : t("Save to apply them"),
        },
      ]}
    />
  );
}
