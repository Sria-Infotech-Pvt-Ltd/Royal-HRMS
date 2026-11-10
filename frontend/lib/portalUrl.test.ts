import { describe, expect, it } from "vitest";
import { validatePortalUrl } from "./portalUrl";

describe("validatePortalUrl", () => {
  it("accepts the production address, with or without a trailing slash", () => {
    expect(validatePortalUrl("https://aira.nxsys.in", true)).toBeNull();
    expect(validatePortalUrl("https://aira.nxsys.in/", true)).toBeNull();
    expect(validatePortalUrl("  https://aira.nxsys.in  ", true)).toBeNull();
  });

  it("allows a blank value (the server then refuses to send invitations until one is set)", () => {
    expect(validatePortalUrl("", true)).toBeNull();
    expect(validatePortalUrl("   ", true)).toBeNull();
  });

  it.each([
    "http://", "http:/", "https://", "aira.nxsys.in", "activate", "http://activate", "https://activate",
    "ftp://aira.nxsys.in", "https://aira nxsys.in", "https://aira.nxsys.in?x=1", "https://aira.nxsys.in#top",
    "//aira.nxsys.in", "javascript:alert(1)",
  ])("rejects the malformed value %s", value => {
    expect(validatePortalUrl(value, true)).not.toBeNull();
  });

  it("requires https in production but allows http://localhost only in development", () => {
    expect(validatePortalUrl("http://aira.nxsys.in", true)).toMatch(/https/);
    expect(validatePortalUrl("http://localhost:3000", true)).toMatch(/https/);
    expect(validatePortalUrl("http://localhost:3000", false)).toBeNull();
    expect(validatePortalUrl("http://aira.nxsys.in", false)).toMatch(/https/);
  });
});
