import { describe, expect, it } from "vitest";
import { buildContactChanges } from "./editRecordContact";

const SAVED = { email: "pat@example.test", mobile: "+91 98765 43210" };

describe("buildContactChanges", () => {
  it("sends nothing for a role that cannot edit, whatever was typed", () => {
    const draft = { personalEmail: "other@example.test", mobileNumber: "9000000000" };
    expect(buildContactChanges(draft, SAVED, false, true)).toEqual({});
  });

  it("sends nothing when nothing changed, even if the mobile is formatted differently", () => {
    const draft = { personalEmail: "PAT@example.test", mobileNumber: "+91 9876543210" };
    expect(buildContactChanges(draft, SAVED, true, false)).toEqual({});
  });

  it("sends a changed mobile alone", () => {
    const draft = { personalEmail: SAVED.email, mobileNumber: "+91 9876511111" };
    expect(buildContactChanges(draft, SAVED, true, false)).toEqual({ phone: "+91 9876511111" });
  });

  it("sends a changed email with the confirmation flag as ticked", () => {
    const draft = { personalEmail: "fixed@example.test", mobileNumber: SAVED.mobile };
    expect(buildContactChanges(draft, SAVED, true, false)).toEqual({ email: "fixed@example.test", confirm_login_email_change: false });
    expect(buildContactChanges(draft, SAVED, true, true)).toEqual({ email: "fixed@example.test", confirm_login_email_change: true });
  });

  it("still sends a blank mobile so the server can explain it is required", () => {
    const draft = { personalEmail: SAVED.email, mobileNumber: "" };
    expect(buildContactChanges(draft, SAVED, true, false)).toEqual({ phone: "" });
  });
});
