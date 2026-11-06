import { describe, expect, it } from "vitest";
import * as consentText from "./consentText";

// Phase 7.4: this module is wording only. The consent VERSION lives on the server (the backend stamps it on every new
// registration and the browser never sends it), so there must be no second copy here that could drift.
describe("consentText (wording only)", () => {
  it("exports exactly the two notices and no version constant", () => {
    expect(Object.keys(consentText).sort()).toEqual(["FACE_CONSENT_NOTICE_EMPLOYEE", "FACE_CONSENT_NOTICE_HR"]);
    expect(consentText).not.toHaveProperty("FACE_CONSENT_TEXT_VERSION");
  });

  it("uses Punch In / Punch Out wording in both notices", () => {
    for (const notice of [consentText.FACE_CONSENT_NOTICE_EMPLOYEE, consentText.FACE_CONSENT_NOTICE_HR]) {
      expect(notice).toContain("Punch In and Punch Out");
      expect(notice).not.toMatch(/clock/i);
    }
  });
});
