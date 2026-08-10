"use client";

// The shared camera + face-detection + liveness engine behind every face
// capture flow in the app: loads models → gets the camera → frames the face →
// runs the liveness challenge → extracts the descriptor, then hands it to the
// caller via onCaptured. What happens with that descriptor (submit it for
// registration approval, or verify it against an approved one at clock-in) is
// entirely up to the caller — this hook knows nothing about either.
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { faceapi, loadFaceApiModels } from "@/lib/faceApi/loadModels";
import { LivenessTracker } from "@/lib/faceApi/liveness";
import { syncCanvasSize, drawDetectionBox, clearOverlay, OVERLAY_COLOR } from "@/lib/faceApi/overlay";

export type LivenessCapturePhase =
  | "idle"
  | "loading_models"
  | "requesting_camera"
  | "camera_denied"
  | "detecting"
  | "liveness_checking"
  | "liveness_failed"
  | "captured"
  | "error";

// ~0.3–0.5s of a consistently detected face before the liveness challenge starts —
// avoids kicking it off on a single lucky frame while the user is still settling in.
const STABLE_FRAMES_TO_START_LIVENESS = 10;
const LIVENESS_TIMEOUT_MS = 9000;
const DETECTOR_OPTIONS = new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 });

type DetectionWithLandmarks = faceapi.WithFaceLandmarks<faceapi.WithFaceDetection<object>>;

interface UseFaceLivenessCaptureOptions {
  /** Fired once with a live, liveness-passed face descriptor. The camera stays
   *  open afterwards (phase moves to "captured") — call stop() once you're
   *  done with the descriptor (e.g. after submitting/verifying it).
   *  captureSessionId is a fresh crypto.randomUUID() minted once per start()
   *  call (one per camera session) — the backend's anti-replay check
   *  (services_face_antispoofing.py) uses it to tell a genuinely fresh
   *  capture apart from a resubmitted one; multiple retries within the SAME
   *  open camera (retry() below) reuse it since it's the same session. */
  onCaptured: (descriptor: number[], livenessScore: number, captureSessionId: string) => void;
}

function generateCaptureSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  // Fallback for a non-secure-context browser where crypto.randomUUID isn't
  // exposed — good enough for a client-side dedup key, not for anything
  // cryptographic.
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

interface UseFaceLivenessCapture {
  phase:        LivenessCapturePhase;
  errorMessage: string | null;
  videoRef:     RefObject<HTMLVideoElement | null>;
  canvasRef:    RefObject<HTMLCanvasElement | null>;
  start:        () => void;
  retry:        () => void;
  stop:         () => void;
}

export function useFaceLivenessCapture(
  { onCaptured }: UseFaceLivenessCaptureOptions,
): UseFaceLivenessCapture {
  const [phase, setPhase] = useState<LivenessCapturePhase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const videoRef  = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef    = useRef<number | null>(null);
  const livenessTrackerRef  = useRef(new LivenessTracker());
  const stableFrameCountRef = useRef(0);
  const livenessStartRef    = useRef(0);
  const captureSessionIdRef = useRef(generateCaptureSessionId()); // re-minted in start() below, once per camera session
  const phaseRef            = useRef<LivenessCapturePhase>("idle"); // read fresh inside the raf loop, avoids stale closures
  const onCapturedRef       = useRef(onCaptured);                  // avoids restarting the loop when the caller's callback identity changes

  useEffect(() => { phaseRef.current = phase; }, [phase]);
  useEffect(() => { onCapturedRef.current = onCaptured; }, [onCaptured]);

  const stopCamera = useCallback(() => {
    if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]); // always release the camera on unmount

  const captureAndFinish = useCallback(async (livenessScore: number) => {
    const video = videoRef.current;
    if (!video) return;
    const result = await faceapi.detectSingleFace(video, DETECTOR_OPTIONS).withFaceLandmarks().withFaceDescriptor();
    if (!result) {
      // Face slipped out of frame at the exact moment of capture — a liveness
      // retry, not a hard error; the challenge itself already succeeded.
      setPhase("liveness_failed");
      return;
    }
    setPhase("captured");
    onCapturedRef.current(Array.from(result.descriptor), livenessScore, captureSessionIdRef.current);
  }, []);

  const handleFrame = useCallback((
    result: DetectionWithLandmarks | undefined,
    canvas: HTMLCanvasElement,
    video: HTMLVideoElement,
  ): boolean => {
    syncCanvasSize(canvas, video);
    const currentPhase = phaseRef.current;

    if (!result) {
      stableFrameCountRef.current = 0;
      clearOverlay(canvas);
      return true;
    }

    const nativeSize = { width: video.videoWidth, height: video.videoHeight };
    const box = result.detection.box;

    if (currentPhase === "detecting") {
      drawDetectionBox(canvas, box, nativeSize, OVERLAY_COLOR.detecting);
      stableFrameCountRef.current += 1;
      if (stableFrameCountRef.current >= STABLE_FRAMES_TO_START_LIVENESS) {
        livenessTrackerRef.current.reset();
        livenessStartRef.current = Date.now();
        setPhase("liveness_checking");
      }
      return true;
    }

    if (currentPhase === "liveness_checking") {
      livenessTrackerRef.current.addSample(result.landmarks);
      const liveness = livenessTrackerRef.current.getResult();
      drawDetectionBox(canvas, box, nativeSize, liveness.passed ? OVERLAY_COLOR.passed : OVERLAY_COLOR.checking);

      if (liveness.passed) {
        void captureAndFinish(liveness.score);
        return false; // capture takes over — stop the detection loop
      }
      if (Date.now() - livenessStartRef.current > LIVENESS_TIMEOUT_MS) {
        setPhase("liveness_failed");
        return false;
      }
    }
    return true;
  }, [captureAndFinish]);

  const runDetectionLoop = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) {
      rafRef.current = requestAnimationFrame(runDetectionLoop);
      return;
    }

    faceapi
      .detectSingleFace(video, DETECTOR_OPTIONS)
      .withFaceLandmarks()
      .then(result => {
        const shouldContinue = handleFrame(result, canvas, video);
        if (shouldContinue) rafRef.current = requestAnimationFrame(runDetectionLoop);
        return undefined;
      })
      .catch(() => { rafRef.current = requestAnimationFrame(runDetectionLoop); });
  }, [handleFrame]);

  const start = useCallback(async () => {
    setErrorMessage(null);
    stableFrameCountRef.current = 0;
    captureSessionIdRef.current = generateCaptureSessionId(); // fresh camera session

    setPhase("loading_models");
    try {
      await loadFaceApiModels();
    } catch (err: unknown) {
      // Logged (not just surfaced as a generic banner) because this failure
      // mode has more than one real cause in practice — e.g. a proxy/rewrite
      // rule intercepting /models/* and returning HTML instead of the actual
      // weight files, not just a genuine network drop — and the console is
      // the only place that distinction is visible.
      console.error("[useFaceLivenessCapture] failed to load face-api models:", err);
      setErrorMessage("Could not load face-recognition models. Check your connection and try again.");
      setPhase("error");
      return;
    }

    setPhase("requesting_camera");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err: unknown) {
      const name = (err as { name?: string })?.name;
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setPhase("camera_denied");
      } else {
        setErrorMessage("Could not access the camera. Please check it isn't in use by another app.");
        setPhase("error");
      }
      return;
    }

    setPhase("detecting");
    rafRef.current = requestAnimationFrame(runDetectionLoop);
  }, [runDetectionLoop]);

  const retry = useCallback(() => {
    setErrorMessage(null);
    stableFrameCountRef.current = 0;
    livenessTrackerRef.current.reset();

    // No live camera yet (denied, or a hard error before/without one) — only option is asking again.
    if (!streamRef.current || phase === "camera_denied" || phase === "error") {
      void start();
      return;
    }
    // Camera is already live — just re-run framing + liveness, no new permission prompt.
    setPhase("detecting");
    rafRef.current = requestAnimationFrame(runDetectionLoop);
  }, [phase, runDetectionLoop, start]);

  const stop = useCallback(() => {
    stopCamera();
    setPhase("idle");
    setErrorMessage(null);
    stableFrameCountRef.current = 0;
    livenessTrackerRef.current.reset();
  }, [stopCamera]);

  return { phase, errorMessage, videoRef, canvasRef, start, retry, stop };
}
