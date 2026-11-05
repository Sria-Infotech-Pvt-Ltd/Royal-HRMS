// The capture-flow numbers and switches that NEXT_PUBLIC_FACE_FLOW_V2 changes, in one pure place so ON and OFF can
// both be tested without a browser. useFaceLivenessCapture and FaceVerificationModal read these; nothing else
// should hard-code them.
//
// OFF restores the original capture UI, framing and timing. It deliberately does NOT restore the original
// liveness policy, the quality gate or the consistency check - those are security policy, not part of the switch.

export interface FlowParams {
  /** Consecutive well-detected preview frames before the liveness challenge starts. */
  stableFramesToStartLiveness: number;
  /** One liveness window, in ms. */
  livenessTimeoutMs: number;
  /** Pause between captured frames, in ms. */
  multiFrameIntervalMs: number;
  /** Framing hints against the dotted guide, and the readiness gate before liveness. */
  readinessGate: boolean;
  /** Preview luminance sampling (feeds the hints, the fill light and the camera boost). */
  luminanceSampling: boolean;
  /** Gradual camera exposure/brightness boost in dim rooms. */
  cameraBoost: boolean;
  /** Dotted oval + reminder line on the capture stage. */
  guideOval: boolean;
}

export function flowParams(v2: boolean): FlowParams {
  return {
    stableFramesToStartLiveness: v2 ? 5 : 10,
    livenessTimeoutMs: v2 ? 9000 : 12000,
    multiFrameIntervalMs: v2 ? 250 : 350,
    readinessGate: v2,
    luminanceSampling: v2,
    cameraBoost: v2,
    guideOval: v2,
  };
}

/**
 * The white "screen as a light" experience on the punch modal. `screenLight`: the backdrop fades to white while the
 * camera preview is live. `fillLight`: additionally show the "raise your screen brightness" tip - only once the
 * preview has been consistently dim. Both are always false with V2 off.
 */
export function fillLightState(v2: boolean, cameraPreviewLive: boolean, lowLight: boolean): { screenLight: boolean; fillLight: boolean } {
  const screenLight = v2 && cameraPreviewLive;
  return { screenLight, fillLight: screenLight && lowLight };
}
