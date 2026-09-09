"use client";

// Shared "loading…" block — replaces the many hand-rolled versions of this
// same spinner+label pattern (each with its own separately-tuned padding/
// height/font-size) scattered across the app. Uses Tailwind's built-in
// `animate-spin` utility rather than a local `@keyframes spin` block (many
// existing call sites each defined their own copy of that same keyframe
// inline — this needs none).

interface Props {
  label?: string;
  /** Fills the available height of its container (e.g. a full-page/full-tab
   * loading state) rather than a compact inline row — use for a section that
   * has nothing else on screen yet while it loads. */
  fullHeight?: boolean;
}

export default function LoadingState({ label = "Loading…", fullHeight = false }: Props) {
  return (
    <div
      style={{
        display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
        padding: fullHeight ? 0 : "40px 24px",
        height: fullHeight ? 200 : undefined,
        color: "var(--on-variant)", fontSize: 13,
      }}
    >
      <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 20 }} />
      {label}
    </div>
  );
}
