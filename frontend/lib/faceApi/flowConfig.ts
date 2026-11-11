// Kill switch for the face-flow reliability changes (live framing hints,
// readiness gate before liveness, auto-resume after a failed attempt,
// constrained camera request, adaptive fill light, adaptive detector size).
//
// Defaults to ON. Set NEXT_PUBLIC_FACE_FLOW_V2=0 at build time to fall back to
// the previous behaviour without a code change. Deliberately does NOT cover
// anything security-relevant: the liveness requirement (blink AND head turn),
// the per-frame quality gate, the multi-frame consistency check and the
// backend match threshold behave identically with the switch on or off.
export const FACE_FLOW_V2: boolean = process.env.NEXT_PUBLIC_FACE_FLOW_V2 !== "0";

// Model-loading reliability changes (loader state machine, recognition model
// download overlapping the detector warm-up, 30 s stall timeout with one
// automatic retry, recognition self-test, final-descriptor validation, honest
// loading messages). Unlike FACE_FLOW_V2 this defaults to OFF: set
// NEXT_PUBLIC_FACE_LOADER_V2=1 at build time to turn it on, unset it to roll
// back. It never touches thresholds, liveness, the quality gate or anything the
// backend matches on.
//
// A function (not a module constant) so tests can flip it at runtime; Next
// still inlines the literal `process.env.NEXT_PUBLIC_...` reference at build.
export function isFaceLoaderV2(): boolean {
  return process.env.NEXT_PUBLIC_FACE_LOADER_V2 === "1";
}
