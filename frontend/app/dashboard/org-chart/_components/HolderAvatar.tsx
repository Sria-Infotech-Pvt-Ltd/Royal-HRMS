"use client";

// The small round picture of a position's holder on the org charts and the unit / position panel: their uploaded profile
// photo when there is one, their initials otherwise, and "?" for a vacant seat. If a photo fails to load, the initials come back.

import { useState, type CSSProperties } from "react";
import { initialsOf } from "@/lib/orgStructureStats";

interface HolderAvatarProps {
  name: string | null;
  photoUrl?: string | null;
  /** The chart's own class (e.g. "oc-avatar"), which sets size and colours. */
  className?: string;
  style?: CSSProperties;
}

export default function HolderAvatar({ name, photoUrl, className, style }: HolderAvatarProps) {
  const [hasFailed, setHasFailed] = useState(false);
  const showPhoto = Boolean(name && photoUrl && !hasFailed);
  return (
    <span className={className} style={{ overflow: "hidden", ...style }} title={name ?? undefined}>
      {showPhoto && photoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- a user-uploaded photo of any size from file storage; next/image would need every storage host configured
        <img src={photoUrl} alt={name ?? ""} onError={() => setHasFailed(true)} style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "inherit", display: "block" }} />
      ) : name ? initialsOf(name) : "?"}
    </span>
  );
}
