"use client";

// Starts downloading + warming the face models after the dashboard has opened
// after login, for every employee whose organisation has face verification
// switched on - not only on pages that render the punch button. By the time
// someone clicks Punch In the models are normally already loaded and warm, so
// the camera opens straight away. Renders nothing; errors are swallowed because
// the capture flow itself retries the load when it is actually needed.
//
// The models are about 7 MB. They wait until the page has finished loading and then a few more seconds, so the dashboard's own
// requests (attendance, leave, requests...) get the connection first: a slow connection was sharing its bandwidth with this download.
import { useEffect } from "react";
import { useFaceVerificationStatus } from "@/hooks/useFaceVerificationStatus";
import { loadFaceApiModels } from "@/lib/faceApi/loadModels";

// How long after the page has loaded the download may begin, and the longest it may then wait for an idle moment.
export const START_DELAY_MS = 4000;
const IDLE_CAP_MS = 3000;

export default function FaceModelPreloader() {
  const { isMandatory } = useFaceVerificationStatus({ asSignedInUser: true });

  useEffect(() => {
    if (!isMandatory) return;
    const run = () => { void loadFaceApiModels().catch(() => undefined); };
    let cancelIdle: () => void = () => undefined;
    let startTimer: number | undefined;
    function scheduleWhenIdle() {
      startTimer = window.setTimeout(() => {
        // Idle time if the browser offers it, with a hard cap so it is never postponed indefinitely.
        if (typeof window.requestIdleCallback === "function") {
          const id = window.requestIdleCallback(run, { timeout: IDLE_CAP_MS });
          cancelIdle = () => window.cancelIdleCallback(id);
        } else {
          run();
        }
      }, START_DELAY_MS);
    }
    const alreadyLoaded = document.readyState === "complete";
    if (alreadyLoaded) scheduleWhenIdle();
    else window.addEventListener("load", scheduleWhenIdle, { once: true });
    return () => {
      window.removeEventListener("load", scheduleWhenIdle);
      if (startTimer !== undefined) window.clearTimeout(startTimer);
      cancelIdle();
    };
  }, [isMandatory]);

  return null;
}
