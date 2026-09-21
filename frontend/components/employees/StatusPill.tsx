"use client";

// Shared status pill for employee-related tables — a colored capsule, not
// tied to any one status enum, so callers (Employee Directory, drawers,
// etc.) can label/tone it for whatever state they're showing (Active,
// Notice Period, Onboarding, Inactive, ...).

export type StatusPillTone = "success" | "warn" | "error" | "neutral";

const TONE_CLASS: Record<StatusPillTone, string> = {
  success: "ok",
  warn:    "warn",
  error:   "crit",
  neutral: "",
};

interface Props {
  label: string;
  tone: StatusPillTone;
}

export default function StatusPill({ label, tone }: Props) {
  return <span className={`chip ${TONE_CLASS[tone]}`}>{label}</span>;
}
