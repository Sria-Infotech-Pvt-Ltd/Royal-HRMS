import { afterEach, describe, expect, it, vi } from "vitest";
import { createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";

// Server-renders the stage (no DOM needed) with the kill switch ON and OFF. The switch is read when the module
// loads, so each case sets NEXT_PUBLIC_FACE_FLOW_V2 first and then imports a fresh copy of the component.
async function render(v2: boolean, props: Record<string, unknown> = {}): Promise<string> {
  vi.resetModules();
  vi.stubEnv("NEXT_PUBLIC_FACE_FLOW_V2", v2 ? "1" : "0");
  const { default: Stage } = await import("./FaceCaptureStage");
  return renderToStaticMarkup(
    <Stage videoRef={createRef<HTMLVideoElement>()} canvasRef={createRef<HTMLCanvasElement>()} phase="detecting" {...props} />,
  );
}

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

describe("FaceCaptureStage with flow V2 ON", () => {
  it("draws the dotted guide oval over the preview, and the place-your-face reminder", async () => {
    const html = await render(true);
    expect(html).toContain("<ellipse");
    expect(html).toContain("stroke-dasharray=\"8 6\"");
    expect(html).toContain("Make sure you place your face inside the frame");
    expect(html).toContain("Put your face exactly inside the dotted lines");
  });

  it("keeps the video, the detection canvas and the 320x240 mirrored preview", async () => {
    const html = await render(true);
    expect(html).toContain("<video");
    expect(html).toContain("<canvas");
    expect(html).toContain("width:320px;height:240px");
    expect(html).toContain("scaleX(-1)");
  });

  it("shows a live framing hint in place of the default line while framing", async () => {
    const html = await render(true, { hint: "Move closer — fill the dotted frame with your face" });
    expect(html).toContain("Move closer");
    expect(html).not.toContain("Put your face exactly inside the dotted lines</div>");
  });

  it("asks for a blink AND a head turn at registration, then prompts for what is still missing", async () => {
    expect(await render(true, { phase: "liveness_checking" })).toContain("blink naturally AND turn your head");
    expect(await render(true, { phase: "liveness_checking", progress: { blink: true, turn: false } })).toContain("now turn your head");
    expect(await render(true, { phase: "liveness_checking", progress: { blink: false, turn: true } })).toContain("now blink naturally");
  });

  it("asks only for a head turn for Punch In / Punch Out (turn_only) and never mentions blinking", async () => {
    const html = await render(true, { phase: "liveness_checking", livenessMode: "turn_only" });
    expect(html).toContain("turn your head slightly to one side");
    expect(html.toLowerCase()).not.toContain("blink");
  });

  it("says to hold still while capturing", async () => {
    expect(await render(true, { phase: "capturing_multi" })).toContain("Hold still");
  });
});

describe("FaceCaptureStage with flow V2 OFF (original behaviour)", () => {
  it("has no dotted oval and no reminder line, and the original framing prompt", async () => {
    const html = await render(false);
    expect(html).not.toContain("<ellipse");
    expect(html).not.toContain("<svg");
    expect(html).not.toContain("Make sure you place your face inside the frame");
    expect(html).toContain("Center your face in the frame");
  });

  it("still renders the preview and the liveness prompts", async () => {
    const html = await render(false, { phase: "liveness_checking" });
    expect(html).toContain("<video");
    expect(html).toContain("<canvas");
    expect(html).toContain("blink naturally AND turn your head");
  });
});
