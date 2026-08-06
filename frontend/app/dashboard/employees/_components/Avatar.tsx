/**
 * Reusable circular avatar. Pass `color` for a department-tinted initials
 * background. Pass `photoUrl` to show a real uploaded profile photo instead —
 * falls back to initials automatically when there's no photo.
 */
export default function Avatar({
  text,
  size = 36,
  color,
  className = "",
  photoUrl,
}: {
  text: string;
  size?: number;
  color?: string;
  className?: string;
  photoUrl?: string | null;
}) {
  if (photoUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- a user-uploaded, arbitrarily-sized Cloudinary URL, not a static/local asset next/image needs to optimise
      <img
        src={photoUrl}
        alt={text}
        className={`rounded-full object-cover flex-shrink-0 ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <div
      className={`rounded-full text-white flex items-center justify-center font-semibold flex-shrink-0 ${color ? "" : "bg-[var(--primary)]"} ${className}`}
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.36),
        ...(color ? { backgroundColor: color } : {}),
      }}
    >
      {text}
    </div>
  );
}
