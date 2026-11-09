import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { FaceRegistrationCardState } from "@/hooks/useFaceRegistrationCard";

// The card takes everything from the server's one Face ID answer, so these cases feed it what the server sends
// for each state of the organisation switch and of the employee's registration.
interface Card {
  state: FaceRegistrationCardState; message: string; canSelfRegister: boolean; notes: string;
  loading: boolean; isMandatory: boolean; fallbackActive: boolean; refetch: () => void;
}
let card: Card;

vi.mock("@/hooks/useFaceRegistrationCard", () => ({ useFaceRegistrationCard: () => card }));
vi.mock("@/components/FaceRegistrationModal", () => ({ default: () => null }));

import EssFaceIdCard from "./EssFaceIdCard";

const render = () => renderToStaticMarkup(<EssFaceIdCard />);

beforeEach(() => {
  card = {
    state: "not_registered", message: "Please register your Face ID first.", canSelfRegister: true, notes: "",
    loading: false, isMandatory: true, fallbackActive: false, refetch: () => {},
  };
});

describe("EssFaceIdCard", () => {
  it("offers Register My Face when Face ID is on and the employee may register", () => {
    const html = render();
    expect(html).toContain("Face ID not yet registered");
    expect(html).toContain("Register My Face");
    expect(html).toContain("Please register your Face ID first.");
  });

  it("shows nothing while Face ID is switched off", () => {
    card = { ...card, state: "disabled", isMandatory: false };
    expect(render()).toBe("");
  });

  it("shows the waiting-for-approval status without an action while HR has not approved", () => {
    card = { ...card, state: "pending", message: "Your Face ID is waiting for approval." };
    const html = render();
    expect(html).toContain("Face ID waiting for approval");
    expect(html).not.toContain("Register My Face");
    expect(html).not.toContain("Update My Face");
  });

  it("shows the registered status and an update action once approved", () => {
    card = { ...card, state: "approved", message: "Your Face ID is registered." };
    const html = render();
    expect(html).toContain("Face ID registered");
    expect(html).toContain("Update My Face");
  });

  it("shows the rejection with HR's reason and lets the employee register again", () => {
    card = { ...card, state: "rejected", notes: "Photo was blurry.", message: "Your registration was rejected." };
    const html = render();
    expect(html).toContain("Face ID registration was rejected");
    expect(html).toContain("Photo was blurry.");
    expect(html).toContain("Update My Face");
  });

  it("gives no action when the organisation registers Face ID in person only", () => {
    card = { ...card, canSelfRegister: false, message: "Please ask HR to register your Face ID." };
    const html = render();
    expect(html).toContain("Please ask HR to register your Face ID.");
    expect(html).not.toContain("Register My Face");
  });
});
