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
import { grabVideoFrame, putImageData, meanLuminanceOfBox, assessEyeOcclusion } from "@/lib/faceApi/frameCapture";
import { applyClahe } from "@/lib/faceApi/clahe";
import {
  assessFrameQuality, computeFrontality, assessCaptureConsistency, averageDescriptors,
  selectFailureMessage, classifyDetectedFaceCount, MULTIPLE_FACES_MESSAGE, EYE_OCCLUSION_MESSAGE,
  type FrameQualityMetrics,
} from "@/lib/faceApi/qualityGate";

export type LivenessCapturePhase =
  | "idle"
  | "loading_models"
  | "requesting_camera"
  | "camera_denied"
  | "detecting"
  | "liveness_checking"
  | "liveness_failed"
  // Post-liveness quality-gated capture — every caller goes through this,
  // averaging framesToCapture quality-gated frames (registration and
  // punch-time verification both use framesToCapture > 1, just different
  // counts — see each caller for its own value).
  | "capturing_multi"
  // The liveness-passed frame(s) didn't clear the per-frame quality gate
  // (lighting/angle/distance/detector confidence), or — in multi-frame mode —
  // didn't agree with each other closely enough to trust an average of them.
  // Distinct from "liveness_failed": liveness itself passed here, it's the
  // CAPTURE quality that didn't.
  | "quality_failed"
  | "captured"
  | "error";

// ~0.3–0.5s of a consistently detected face before the liveness challenge starts —
// avoids kicking it off on a single lucky frame while the user is still settling in.
const STABLE_FRAMES_TO_START_LIVENESS = 10;
const LIVENESS_TIMEOUT_MS = 9000;
const DETECTOR_OPTIONS = new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 });

// ─── Quality-gated capture (used by every caller, framesToCapture >= 1) ────
// Spacing between captured frames — long enough that consecutive frames
// aren't near-duplicates of each other (defeating the point of sampling
// multiple moments), short enough that the whole capture still feels
// instant to the person holding a pose. Irrelevant when framesToCapture is 1
// (no sleep happens before the first, only, attempt).
const MULTI_FRAME_INTERVAL_MS = 350;
// Frames can fail the quality gate (blink, micro-movement, momentary
// shadow) without the whole capture failing — this bounds how many EXTRA
// attempts are allowed before giving up and asking for a full retry, rather
// than looping forever against consistently bad conditions. At
// framesToCapture === 1 (punch-time) this caps a bad capture at 4 quick
// attempts before surfacing "quality_failed" and asking the employee to
// recapture, instead of ever running a match against a low-quality frame.
const MULTI_FRAME_ATTEMPTS_PER_TARGET_FRAME = 4;
// How far apart (Euclidean distance, same units as FACE_MATCH_MAX_DISTANCE
// on the backend) this capture's own frames are allowed to be from each
// other before they're treated as an inconsistent session rather than
// averaged — see qualityGate.ts's assessCaptureConsistency. Tighter than
// FACE_MATCH_MAX_DISTANCE (0.6) on purpose: these are supposed to be several
// near-identical moments of the SAME short capture, not independent
// same-person verifications, so they should agree much more closely than
// the punch-time match bar requires.
const MAX_INTRA_CAPTURE_DISTANCE = 0.35;

type DetectionWithLandmarks = faceapi.WithFaceLandmarks<faceapi.WithFaceDetection<object>>;

/** Present only when framesToCapture > 1 and the composite descriptor is an
 *  average of multiple quality-gated frames — see FaceRegistrationRequest's
 *  capture_frame_count/capture_variance fields, which this maps directly onto. */
export interface CaptureQualityMeta {
  frameCount: number;
  variance: number;
}

/** Result of one captureOneQualityGatedFrame attempt. `reasons` is only ever
 *  non-empty when a face WAS found but the attempt was rejected for an
 *  identifiable cause (quality-gate check, multiple faces, suspected
 *  occlusion) — it stays empty for "no face detected this instant", which
 *  isn't attributable to anything specific. See qualityGate.ts's
 *  selectFailureMessage for how a sequence of these becomes one message. */
interface QualityGatedFrameAttempt {
  descriptor: number[] | null;
  reasons: string[];
}

interface UseFaceLivenessCaptureOptions {
  /** Fired once with a live, liveness-passed face descriptor. The camera stays
   *  open afterwards (phase moves to "captured") — call stop() once you're
   *  done with the descriptor (e.g. after submitting/verifying it).
   *  captureSessionId is a fresh crypto.randomUUID() minted once per start()
   *  call (one per camera session) — the backend's anti-replay check
   *  (services_face_antispoofing.py) uses it to tell a genuinely fresh
   *  capture apart from a resubmitted one; multiple retries within the SAME
   *  open camera (retry() below) reuse it since it's the same session.
   *  captureQuality is set only in multi-frame mode — see CaptureQualityMeta. */
  onCaptured: (
    descriptor: number[], livenessScore: number, captureSessionId: string, captureQuality?: CaptureQualityMeta,
  ) => void;
  /** How many quality-gated frames to average into the final descriptor.
   *  Defaults to 1 — a single quality-gated frame, still subject to the same
   *  per-frame quality gate (lib/faceApi/qualityGate.ts) as a multi-frame
   *  capture, just with no cross-frame averaging/consistency check (nothing
   *  to average) — only used where a caller explicitly opts into it (there
   *  currently isn't one; every real caller passes framesToCapture > 1, see
   *  below). Registration hooks (useFaceRegistrationCapture, useHRFaceCapture)
   *  pass 4 — a registered face is a long-lived reference, worth a few extra
   *  seconds to get right the first time (see the mismatch investigation
   *  that motivated this: a single marginal frame becoming someone's
   *  permanent reference left almost no margin against impostors). Punch-time
   *  verification (FaceVerificationModal) passes 3 — fewer than registration
   *  since clock-in/out happens far more often and needs to stay reasonably
   *  quick, but no longer a single unaveraged frame either: a since-confirmed
   *  false-accept incident traced a different person's live capture matching
   *  a genuine reference at distance 0.578 (threshold 0.6) against a
   *  single-frame probe, close enough to this employee's own genuine range
   *  (which reached 0.554) that the single-frame noise band was the
   *  deciding factor, not the identities involved. */
  framesToCapture?: number;
  /** Apply CLAHE lighting normalization (lib/faceApi/clahe.ts) to the frame
   *  before detection. Applies regardless of framesToCapture — both
   *  registration and punch-time verification pass true, so the live capture
   *  compared against a registered reference gets the same lighting
   *  normalization the reference itself was built from. */
  normalizeLighting?: boolean;
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
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
  { onCaptured, framesToCapture = 1, normalizeLighting = false }: UseFaceLivenessCaptureOptions,
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
  // Offscreen canvas used by the quality-gated capture path (grabVideoFrame/
  // applyClahe operate on this, never on the visible overlay canvasRef
  // above) — created lazily on first use, one per hook instance.
  const workingCanvasRef    = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => { phaseRef.current = phase; }, [phase]);
  useEffect(() => { onCapturedRef.current = onCaptured; }, [onCaptured]);

  const stopCamera = useCallback(() => {
    if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]); // always release the camera on unmount

  // One quality-gated frame, used by every capture (registration's
  // multi-frame average AND punch-time's single frame alike): grabs the
  // video's current frame onto the offscreen working canvas, optionally
  // CLAHE-normalizes it, runs detection+descriptor on THAT canvas (not the
  // raw video — this is what makes the lighting normalization actually
  // reach face-api.js instead of just existing for nothing), and scores it.
  //
  // Uses detectAllFaces (not detectSingleFace) specifically HERE — the still
  // frame that's actually a candidate to become the descriptor — rather than
  // in the continuous live-preview loop below (runDetectionLoop), which only
  // draws the overlay box and feeds the liveness tracker and never produces
  // anything that gets stored or matched. Checking face count on every
  // preview frame (~60/s) would be wasted work for no benefit and would
  // false-trigger on anyone briefly passing through the background during
  // the "hold still" framing stage; checking it only on the handful of
  // frames actually sampled here means a transient second face self-heals
  // across retries (see captureMultipleFrames) exactly like a transient bad
  // angle or shadow already does, and only becomes a surfaced message if it
  // persists through every attempt.
  //
  // Returns descriptor: null for "no usable frame this attempt" (no face
  // detected, multiple faces, quality-gate rejection, or suspected
  // occlusion) — callers retry rather than treating this as fatal. `reasons`
  // carries the specific, user-facing cause when one is known.
  const captureOneQualityGatedFrame = useCallback(async (): Promise<QualityGatedFrameAttempt> => {
    const video = videoRef.current;
    if (!video) return { descriptor: null, reasons: [] };
    if (!workingCanvasRef.current) workingCanvasRef.current = document.createElement("canvas");
    const workingCanvas = workingCanvasRef.current;

    let imageData: ImageData;
    try {
      imageData = grabVideoFrame(video, workingCanvas);
    } catch {
      return { descriptor: null, reasons: [] }; // video not ready this instant — try again next attempt
    }
    if (normalizeLighting) {
      applyClahe(imageData);
      putImageData(workingCanvas, imageData);
    }

    const results = await faceapi.detectAllFaces(workingCanvas, DETECTOR_OPTIONS).withFaceLandmarks().withFaceDescriptors();
    const faceCount = classifyDetectedFaceCount(results.length);
    if (faceCount === 'none') return { descriptor: null, reasons: [] };
    if (faceCount === 'multiple') return { descriptor: null, reasons: [MULTIPLE_FACES_MESSAGE] };

    const result = results[0];
    const nose = result.landmarks.getNose();
    const metrics: FrameQualityMetrics = {
      detectionScore: result.detection.score,
      faceWidthRatio: result.detection.box.width / video.videoWidth,
      frontality: computeFrontality(result.landmarks.getLeftEye(), result.landmarks.getRightEye(), nose[3]),
      meanLuminance: meanLuminanceOfBox(imageData, result.detection.box),
    };
    const quality = assessFrameQuality(metrics);
    if (!quality.passed) return { descriptor: null, reasons: quality.reasons };

    // Only reached once the frame otherwise looks acceptable (good
    // confidence, well-framed, well-lit overall) — see assessEyeOcclusion's
    // own docstring for why running this only after the rest of the gate
    // already passed is what keeps it conservative.
    const occlusion = assessEyeOcclusion(imageData, result.landmarks.getLeftEye(), result.landmarks.getRightEye());
    if (occlusion.suspected) return { descriptor: null, reasons: [EYE_OCCLUSION_MESSAGE] };

    return { descriptor: Array.from(result.descriptor), reasons: [] };
  }, [normalizeLighting]);

  // After liveness already passed once, collect `framesToCapture`
  // quality-gated frame(s) and average them — see this file's module
  // docstring and the qualityGate.ts/clahe.ts modules for why. At
  // framesToCapture === 1 (punch-time) this is a single quality-gated frame
  // with no averaging or cross-frame consistency check to fail (a lone
  // frame trivially "agrees with itself" — see assessCaptureConsistency);
  // at framesToCapture > 1 (registration) both the per-frame gate AND the
  // cross-frame consistency check must pass. Never calls onCaptured with a
  // capture that didn't clear the gate(s) that apply; phase moves to
  // "quality_failed" instead, same retry shape as "liveness_failed".
  const captureMultipleFrames = useCallback(async (livenessScore: number) => {
    setPhase("capturing_multi");

    const collected: number[][] = [];
    const reasonsPerAttempt: string[][] = [];
    const maxAttempts = framesToCapture * MULTI_FRAME_ATTEMPTS_PER_TARGET_FRAME;
    for (let attempt = 0; attempt < maxAttempts && collected.length < framesToCapture; attempt++) {
      if (attempt > 0) await sleep(MULTI_FRAME_INTERVAL_MS);
      const { descriptor, reasons } = await captureOneQualityGatedFrame();
      if (descriptor) collected.push(descriptor);
      else reasonsPerAttempt.push(reasons);
    }

    if (collected.length < framesToCapture) {
      // The most recent attempt with an identifiable cause wins (see
      // selectFailureMessage) — falls back to the old generic copy only
      // when no attempt ever pinned down a specific reason (e.g. a face was
      // never detected at all).
      const specificReason = selectFailureMessage(reasonsPerAttempt);
      setErrorMessage(
        specificReason
        ?? (framesToCapture > 1
          ? "Couldn't get enough clear captures — make sure you're well-lit, centered, and holding still, then try again."
          : "Couldn't get a clear capture — make sure you're well-lit, centered, and holding still, then try again."),
      );
      setPhase("quality_failed");
      return;
    }

    const consistency = assessCaptureConsistency(collected, MAX_INTRA_CAPTURE_DISTANCE);
    if (!consistency.passed) {
      setErrorMessage("Your captures didn't quite agree with each other — hold still and try again.");
      setPhase("quality_failed");
      return;
    }

    setPhase("captured");
    onCapturedRef.current(averageDescriptors(collected), livenessScore, captureSessionIdRef.current, {
      frameCount: collected.length,
      variance: consistency.meanPairwiseDistance,
    });
  }, [framesToCapture, captureOneQualityGatedFrame]);

  const captureAndFinish = useCallback(async (livenessScore: number) => {
    await captureMultipleFrames(livenessScore);
  }, [captureMultipleFrames]);

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
