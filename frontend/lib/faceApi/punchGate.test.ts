import { describe, expect, it } from "vitest";
import { faceGateFor } from "./punchGate";
import type { FaceIdFallbackPolicy, FaceIdMode, FaceIdState } from "@/types/faceId";

// The server turns (mode, state, fallback policy) into the three flags below; this mirrors that contract exactly:
// requires_face_to_punch is true only for an approved Face ID, whatever the mode.
const STATES: FaceIdState[] = ["approved", "pending", "rejected", "not_registered"];
const MODES: FaceIdMode[] = ["self_service", "hr_in_person", "self_service_hr_approval"];
const FALLBACKS: FaceIdFallbackPolicy[] = ["none", "days_after_joining", "until_approved"];

function serverFlags(state: FaceIdState, fallbackActive: boolean) {
  return { isMandatory: true, requiresFaceToPunch: state === "approved", fallbackActive: state !== "approved" && fallbackActive };
}

describe("faceGateFor - Face ID not mandatory", () => {
  it("never opens the camera and never blocks, whatever the person's state", () => {
    for (const state of STATES) {
      const gate = faceGateFor({ ...serverFlags(state, false), isMandatory: false });
      expect(gate).toEqual({ faceVerificationRequired: false, faceRegistrationMissing: false });
    }
  });
});

describe("faceGateFor - Face ID mandatory, no fallback", () => {
  it("an approved employee opens the face camera and is not blocked", () => {
    expect(faceGateFor(serverFlags("approved", false))).toEqual({ faceVerificationRequired: true, faceRegistrationMissing: false });
  });

  it.each(["not_registered", "pending", "rejected"] as FaceIdState[])(
    "a %s employee is stopped before GPS and the camera: register first, then come back",
    (state) => {
      expect(faceGateFor(serverFlags(state, false))).toEqual({ faceVerificationRequired: false, faceRegistrationMissing: true });
    },
  );
});

describe("faceGateFor - fallback", () => {
  it.each(["not_registered", "pending", "rejected"] as FaceIdState[])(
    "while the fallback applies, a %s employee may punch without the camera (the server flags it for HR)",
    (state) => {
      expect(faceGateFor(serverFlags(state, true))).toEqual({ faceVerificationRequired: false, faceRegistrationMissing: false });
    },
  );

  it("an approved employee still verifies their face even if a fallback happens to be configured", () => {
    expect(faceGateFor(serverFlags("approved", true))).toEqual({ faceVerificationRequired: true, faceRegistrationMissing: false });
  });
});

describe("faceGateFor - every registration mode x fallback policy x state", () => {
  // The three registration modes only change WHO registers and whether HR approves; the punch gate depends solely
  // on whether an approved Face ID exists (and the fallback), which is what the server reports.
  it("only an approved Face ID ever opens the camera; no one else gets past without a fallback", () => {
    for (const mode of MODES) {
      for (const policy of FALLBACKS) {
        for (const state of STATES) {
          const fallbackActive = policy !== "none"; // the server would only report true while the policy applies
          const gate = faceGateFor(serverFlags(state, fallbackActive));
          const label = `${mode}/${policy}/${state}`;
          expect(gate.faceVerificationRequired, label).toBe(state === "approved");
          expect(gate.faceRegistrationMissing, label).toBe(state !== "approved" && policy === "none");
          // Never both at once: a person is either asked for a face or told to register, not both.
          expect(gate.faceVerificationRequired && gate.faceRegistrationMissing, label).toBe(false);
        }
      }
    }
  });
});
