import { describe, expect, it } from "vitest";
import { NO_MATCH_INTENT as libNoMatch } from "@/lib/voiceHindiRecovery";
import {
  BARGE_IN_ENABLED, LOCATION_PERMISSION_DENIED_MESSAGE, NO_MATCH_INTENT, GEOFENCE_REQUIRED_MESSAGE,
} from "./useVoiceCommand.constants";

describe("voice constants", () => {
  it("barge-in stays disabled (Phase 5 must not enable interruption behavior)", () => {
    expect(BARGE_IN_ENABLED).toBe(false);
  });

  it("has one source for NO_MATCH_INTENT: the constants file re-exports the recovery lib's value", () => {
    expect(NO_MATCH_INTENT).toBe(libNoMatch);
    expect(NO_MATCH_INTENT).toBe("no_match");
  });

  it("location-permission message uses Punch In/Out wording, matching useClockWidget", () => {
    expect(LOCATION_PERMISSION_DENIED_MESSAGE).toBe(
      "Location access is required for office punch in/out. Please allow location in your browser settings.",
    );
  });

  it("keeps the geofence message identical to the unchanged backend string", () => {
    expect(GEOFENCE_REQUIRED_MESSAGE).toBe(
      "Your location is required to clock in at this branch. Please allow location access in your browser and try again.",
    );
  });
});
