"use client";

// Starts downloading + warming the face models as soon as the dashboard opens
// after login, for every employee whose organisation has face verification
// switched on — not only on pages that render the clock button, and without
// waiting for the approval-status request. By the time someone clicks Clock
// In the models are normally already loaded and warm, so the camera opens
// straight away. Renders nothing; errors are swallowed because the clock-in
// flow itself retries the load when it is actually needed.
import { useEffect } from "react";
import { useFaceVerificationStatus } from "@/hooks/useFaceVerificationStatus";
import { scheduleFaceModelPreload } from "@/lib/faceApi/preload";

export default function FaceModelPreloader() {
  const { isMandatory } = useFaceVerificationStatus();

  useEffect(() => {
    if (!isMandatory) return;
    // The one shared scheduler (lib/faceApi/preload.ts): idle-time, once, even
    // though the clock widget asks for the same preload.
    return scheduleFaceModelPreload();
  }, [isMandatory]);

  return null;
}
