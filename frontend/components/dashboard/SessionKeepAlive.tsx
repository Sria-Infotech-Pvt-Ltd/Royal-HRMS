"use client";

import { useSessionKeepAlive } from "@/hooks/useSessionKeepAlive";

/** Draws nothing: mounts the quiet login renewal for every dashboard page. */
export default function SessionKeepAlive() {
  useSessionKeepAlive();
  return null;
}
