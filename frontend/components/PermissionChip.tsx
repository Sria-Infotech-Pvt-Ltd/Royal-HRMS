"use client";

import { useT } from "@/hooks/useI18n";

interface PermissionChipProps {
  label: string;
  isOn: boolean;
  isDisabled?: boolean;
  isSensitive?: boolean;
  title?: string;
  /** Where an already-held permission comes from ("everyone", "their seat"): shown small beside the label. */
  note?: string;
  onToggle: () => void;
}

/** One permission as a pill that toggles: a plus when off, a tick when on, a small warning mark when it is sensitive. */
export default function PermissionChip({ label, isOn, isDisabled = false, isSensitive = false, title, note, onToggle }: PermissionChipProps) {
  const t = useT();
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={isOn}
      aria-label={label}
      disabled={isDisabled}
      onClick={onToggle}
      title={title}
      className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11.5px] font-semibold capitalize transition-colors disabled:cursor-not-allowed"
      style={isOn
        ? { background: "color-mix(in srgb, var(--primary) 12%, transparent)", borderColor: "var(--primary)", color: "var(--primary)", opacity: isDisabled ? 0.7 : 1 }
        : { background: "var(--surface)", borderColor: "var(--outline-v)", color: "var(--on-variant)", opacity: isDisabled ? 0.6 : 1 }}
    >
      <i className={`ti ${isDisabled && isOn ? "ti-lock" : isOn ? "ti-check" : "ti-plus"} text-[11px]`} />
      {label}
      {note && <span className="text-[10px] font-medium normal-case opacity-80">({note})</span>}
      {isSensitive && <i className="ti ti-alert-triangle" style={{ color: "var(--warn)" }} aria-label={t("Sensitive permission")} />}
    </button>
  );
}
