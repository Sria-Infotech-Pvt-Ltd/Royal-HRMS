// Kill switch for the face-flow reliability changes: the dotted-guide framing
// hints, the readiness gate before liveness, the white screen fill light, the
// camera brightness boost and the faster frame spacing.
//
// Defaults to ON. Set NEXT_PUBLIC_FACE_FLOW_V2=0 at build time to fall back to
// the previous behaviour without a code change. Deliberately does NOT cover
// anything security-relevant: the liveness requirement (blink AND head turn at
// registration, head turn at punch), the per-frame quality gate, the
// multi-frame consistency check and the backend match threshold behave
// identically with the switch on or off. Model loading, the wake lock and
// telemetry are performance/diagnostic plumbing and are not switched either.
export const FACE_FLOW_V2: boolean = process.env.NEXT_PUBLIC_FACE_FLOW_V2 !== "0";
