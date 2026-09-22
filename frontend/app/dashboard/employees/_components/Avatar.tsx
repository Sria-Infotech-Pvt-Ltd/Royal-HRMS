/**
 * Reusable circular avatar. Pass `color` for a department-tinted initials
 * background. Pass `photoUrl` to show a real uploaded profile photo instead —
 * falls back to initials automatically when there's no photo.
 */
export default function Avatar({
  text,
  size = 36,
  color,
  textColor,
  shape = "circle",
  className = "",
  photoUrl,
}: {
  text: string;
  size?: number;
  color?: string;
  /** Overrides the default white glyph color — used for light HSL-tinted
   * backgrounds (e.g. the Employee Directory table) where white text
   * wouldn't be readable. */
  textColor?: string;
  /** The reference table row's avatar is a rounded square (10px radius),
   * not circular — confirmed from the reference DOM's `.who .av` rule.
   * Every other usage (header, drawer, profile) stays circular. */
  shape?: "circle" | "square";
  className?: string;
  photoUrl?: string | null;
}) {
  const shapeClass = shape === "square" ? "rounded-[10px]" : "rounded-full";

  if (photoUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- a user-uploaded, arbitrarily-sized Cloudinary URL, not a static/local asset next/image needs to optimise
      <img
        src={photoUrl}
        alt={text}
        className={`${shapeClass} object-cover flex-shrink-0 ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <div
      className={`${shapeClass} flex items-center justify-center font-semibold flex-shrink-0 ${className}`}
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.36),
        // Plain Tailwind utilities (rounded-full, flex-shrink-0, etc.) compile
        // fine under this project's Tailwind v2 JIT pipeline, but arbitrary
        // values containing a CSS var() call — e.g. the `bg-[var(--primary)]`
        // / `text-white` classes this used to conditionally apply — never
        // made it into the compiled CSS at all (confirmed empty across every
        // build chunk), leaving the initials fallback with no background.
        // Inline styles sidestep that JIT gap entirely, matching the pattern
        // already used here for the `color`/`textColor` props.
        backgroundColor: color ?? "var(--primary)",
        // var(--on-primary), not a literal white, so the default (no custom
        // `color` prop) stays readable against --primary's dark-mode tone too.
        color: textColor ?? "var(--on-primary)",
      }}
    >
      {text}
    </div>
  );
}
