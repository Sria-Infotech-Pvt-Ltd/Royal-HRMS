import { describe, expect, it } from "vitest";
import { faceInsideGuide, GUIDE } from "./guide";

const VIDEO_4_3 = { width: 640, height: 480 };
const VIDEO_16_9 = { width: 1280, height: 720 };
const box = (cx: number, cy: number, size = 120) => ({ x: cx - size / 2, y: cy - size / 2, width: size, height: size });

describe("faceInsideGuide", () => {
  it("accepts a face centred in the frame", () => {
    expect(faceInsideGuide(box(320, 240), VIDEO_4_3)).toBe(true);
  });

  it("rejects a face far off to a side or at an edge", () => {
    expect(faceInsideGuide(box(60, 240), VIDEO_4_3)).toBe(false);
    expect(faceInsideGuide(box(600, 240), VIDEO_4_3)).toBe(false);
    expect(faceInsideGuide(box(320, 30), VIDEO_4_3)).toBe(false);
  });

  it("is symmetric left/right (the preview is mirrored)", () => {
    expect(faceInsideGuide(box(320 - 50, 240), VIDEO_4_3)).toBe(faceInsideGuide(box(320 + 50, 240), VIDEO_4_3));
  });

  it("allows more vertical than horizontal drift, like the oval", () => {
    const horizontalEdge = (GUIDE.widthFraction / 2) * 640 * 1.1; // just outside horizontally
    expect(faceInsideGuide(box(320 + horizontalEdge, 240), VIDEO_4_3)).toBe(false);
    expect(faceInsideGuide(box(320, 240 + horizontalEdge), VIDEO_4_3)).toBe(true); // same offset vertically is fine
  });

  it("accounts for the cover-crop of a 16:9 camera shown in the 4:3 preview", () => {
    // Centre of a 16:9 frame is still the centre of the preview.
    expect(faceInsideGuide(box(640, 360), VIDEO_16_9)).toBe(true);
    // A face at 70% across a 16:9 frame is only ~62% across the CROPPED preview => outside the oval's 22% half-width? (0.5+0.2/0.75=0.77 → outside)
    expect(faceInsideGuide(box(1280 * 0.7, 360), VIDEO_16_9)).toBe(false);
    // Slightly off-centre inside the visible crop is fine.
    expect(faceInsideGuide(box(1280 * 0.55, 360), VIDEO_16_9)).toBe(true);
  });

  it("never blocks when the video size is not known yet", () => {
    expect(faceInsideGuide(box(10, 10), { width: 0, height: 0 })).toBe(true);
  });
});
