"use client";

// A value that depends on the viewer's clock, locale or time zone ("today", "3 min ago") must not be rendered on the server: the
// server's answer differs from the browser's and React reports a hydration mismatch (error #418). This returns `initial` for the
// server render and the first browser render, then the real value. Pass a module-level `compute` so it stays stable.

import { useEffect, useState } from "react";

export function useAfterMount<T>(compute: () => T, initial: T): T {
  const [value, setValue] = useState<T>(initial);
  useEffect(() => { setValue(compute()); }, [compute]);
  return value;
}
