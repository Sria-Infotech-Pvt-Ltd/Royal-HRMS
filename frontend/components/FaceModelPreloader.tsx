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
import { loadFaceApiModels } from "@/lib/faceApi/loadModels";

export default function FaceModelPreloader() {
  const { isMandatory } = useFaceVerificationStatus();

  useEffect(() => {
    if (!isMandatory) return;
    const run = () => { void loadFaceApiModels().catch(() => undefined); };
    // Short idle window so the dashboard's own first paint is not competing for
    // the network, but a hard 1s cap so it can never be postponed indefinitely.
    if (typeof window.requestIdleCallback === "function") {
      const id = window.requestIdleCallback(run, { timeout: 1000 });
      return () => window.cancelIdleCallback(id);
    }
    const id = window.setTimeout(run, 300);
    return () => window.clearTimeout(id);
  }, [isMandatory]);

  return null;
}
