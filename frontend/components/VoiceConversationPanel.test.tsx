// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import VoiceConversationPanel from "./VoiceConversationPanel";

function renderPanel(lockoutSecondsRemaining?: number, phase: "greeting" | "result" = "greeting") {
  return render(
    <VoiceConversationPanel
      transcript="punch in"
      message="Too many failed face verification attempts."
      phase={phase}
      isListening={false}
      isProcessing={false}
      interimTranscript=""
      onStartListening={vi.fn()}
      onStopListening={vi.fn()}
      onSubmitText={vi.fn()}
      onClose={vi.fn()}
      isMuted={false}
      onToggleMute={vi.fn()}
      isListeningForInterruption={false}
      history={[]}
      lockoutSecondsRemaining={lockoutSecondsRemaining}
    />,
  );
}

afterEach(() => cleanup());

describe("VoiceConversationPanel lockout status", () => {
  it("shows the countdown in a role=status region while a lockout is active", () => {
    renderPanel(75);
    const status = screen.getByRole("status");
    expect(status.textContent).toContain("Face check locked. Try again in 01:15");
    expect(status.getAttribute("data-testid")).toBe("voice-lockout-status");
  });

  it("renders no lockout status when the lockout is 0 or the prop is omitted", () => {
    renderPanel(0);
    expect(screen.queryByTestId("voice-lockout-status")).toBeNull();
    cleanup();
    renderPanel();
    expect(screen.queryByTestId("voice-lockout-status")).toBeNull();
  });

  it("shows it in the result phase too", () => {
    renderPanel(10, "result");
    expect(screen.getByRole("status").textContent).toContain("00:10");
  });

  it("keeps the typed input and the quick chips usable while locked (other commands still work)", () => {
    renderPanel(75);
    expect(screen.getByPlaceholderText("Or type your answer…")).toBeTruthy();
    expect(screen.getByTestId("voice-quick-action-punch-in")).toBeTruthy();
    expect((screen.getByTestId("voice-quick-action-punch-in") as HTMLButtonElement).disabled).toBe(false);
  });
});
