"use client";

import { useSyncExternalStore } from "react";
import {
  getModelLoadInfo, modelLoadingMessage, subscribeModelLoadState, type ModelLoadPhase,
} from "@/lib/faceApi/loadModels";

const SERVER_PHASE: ModelLoadPhase = "preparing";

/**
 * Text for the "Preparing face verification" loading panel that reflects what the
 * loader is actually doing: "Downloading…" only while model bytes are being
 * fetched, "Preparing…" while they initialise / warm up (including when the files
 * came straight from the browser cache). With NEXT_PUBLIC_FACE_LOADER_V2 off it
 * returns the original wording.
 */
export function useModelLoadMessage(): string {
  const phase = useSyncExternalStore(
    subscribeModelLoadState,
    () => getModelLoadInfo().phase,
    () => SERVER_PHASE,
  );
  return modelLoadingMessage(phase);
}
