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
