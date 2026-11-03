import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

// The banner takes everything from the server's one Face ID answer, so these cases feed it what the server sends
// for each organisation mode, employee state and fallback.
interface Status {
  isMandatory: boolean; state: "approved" | "pending" | "rejected" | "not_registered";
  canSelfRegister: boolean; message: string; loading: boolean; refetch: () => void;
}
let status: Status;
let pathname = "/dashboard/ess";

vi.mock("@/hooks/useFaceVerificationStatus", () => ({ useFaceVerificationStatus: () => status }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@/components/FaceRegistrationModal", () => ({ default: () => null }));

import FaceRegistrationBanner from "./FaceRegistrationBanner";

const render = () => renderToStaticMarkup(<FaceRegistrationBanner />);

beforeEach(() => {
  pathname = "/dashboard/ess";
  status = {
    isMandatory: true, state: "not_registered", canSelfRegister: true, loading: false, refetch: () => {},
    message: "Please register your Face ID first, then come back to punch in.",
  };
});

describe("FaceRegistrationBanner visibility", () => {
  it("is hidden when Face ID is not mandatory", () => {
    status = { ...status, isMandatory: false };
    expect(render()).toBe("");
  });

  it("is hidden once the Face ID is approved", () => {
    status = { ...status, state: "approved", canSelfRegister: true, message: "Your Face ID is registered." };
    expect(render()).toBe("");
  });

  it("is hidden while the status is still loading", () => {
    status = { ...status, loading: true };
    expect(render()).toBe("");
  });

  it("only appears on the dashboard home pages, never inside other modules", () => {
    for (const path of ["/dashboard/leave", "/dashboard/payroll", "/dashboard/my-attendance", "/dashboard/profile"]) {
      pathname = path;
      expect(render(), path).toBe("");
    }
    for (const path of ["/dashboard", "/dashboard/ess", "/dashboard/team"]) {
      pathname = path;
      expect(render(), path).toContain("Register your Face ID");
    }
  });
});

describe("FaceRegistrationBanner by registration mode and status", () => {
  it("self_service / not registered: shows the server message and the Register My Face action", () => {
    const html = render();
    expect(html).toContain("Register your Face ID");
    expect(html).toContain("Please register your Face ID first, then come back to punch in.");
    expect(html).toContain("Register My Face");
  });

  it("self_service_hr_approval / pending: explains it is waiting for HR, with no register action", () => {
    status = { ...status, state: "pending", canSelfRegister: false, message: "Your Face ID has been submitted and is waiting for HR approval." };
    const html = render();
    expect(html).toContain("Face ID waiting for approval");
    expect(html).toContain("waiting for HR approval");
    expect(html).not.toContain("Register My Face");
  });

  it("rejected (employees may register): says so and offers Register My Face again", () => {
    status = { ...status, state: "rejected", canSelfRegister: true, message: "Your Face ID registration was rejected. Please register it again." };
    const html = render();
    expect(html).toContain("Face ID registration was rejected");
    expect(html).toContain("Register My Face");
  });

  it("hr_in_person / not registered: tells them to ask HR and offers NO self-registration button", () => {
    status = { ...status, state: "not_registered", canSelfRegister: false, message: "Your Face ID is registered in person by HR. Please ask HR to register it." };
    const html = render();
    expect(html).toContain("ask HR to register it");
    expect(html).not.toContain("Register My Face");
  });

  it("shows the server's fallback note as-is (the banner adds no policy of its own)", () => {
    status = { ...status, message: "Please register your Face ID first. Until then you can still punch in from your office location; those punches are flagged for HR." };
    expect(render()).toContain("flagged for HR");
  });

  it("can always be dismissed", () => {
    expect(render()).toContain("aria-label=\"Dismiss\"");
  });
});
