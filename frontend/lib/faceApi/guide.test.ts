import { describe, expect, it } from "vitest";
import { GUIDE, faceInsideGuide } from "./guide";

const V43 = { width: 640, height: 480 }; // 4:3 camera - the preview shows all of it
const V169 = { width: 1280, height: 720 }; // 16:9 camera - the preview crops the sides (object-fit: cover)

/** A face box of `w`x`h` centred at fraction (cx, cy) of the video. */
function boxAt(video: { width: number; height: number }, cx: number, cy: number, w = 200, h = 240) {
  return { x: video.width * cx - w / 2, y: video.height * cy - h / 2, width: w, height: h };
}

describe("faceInsideGuide", () => {
  it("accepts a face centred in the frame", () => {
    expect(faceInsideGuide(boxAt(V43, 0.5, 0.5), V43)).toBe(true);
  });

  it("rejects a face pushed to a corner or the far edge", () => {
    expect(faceInsideGuide(boxAt(V43, 0.1, 0.1), V43)).toBe(false);
    expect(faceInsideGuide(boxAt(V43, 0.9, 0.9), V43)).toBe(false);
    expect(faceInsideGuide(boxAt(V43, 0.95, 0.5), V43)).toBe(false);
  });

  it("uses the oval, not a rectangle: a point inside the bounding box but outside the ellipse fails", () => {
    // Bounding box of the oval is 0.44 wide x 0.8 tall; this centre is within it at the corner of that box.
    const cx = 0.5 + GUIDE.widthFraction / 2 - 0.01;
    const cy = 0.5 + GUIDE.heightFraction / 2 - 0.01;
    expect(faceInsideGuide(boxAt(V43, cx, cy), V43)).toBe(false);
  });

  it("allows more sideways drift than the oval's width would suggest for a tall oval, but not past its half-width", () => {
    expect(faceInsideGuide(boxAt(V43, 0.5 + GUIDE.widthFraction / 2 - 0.03, 0.5), V43)).toBe(true);
    expect(faceInsideGuide(boxAt(V43, 0.5 + GUIDE.widthFraction / 2 + 0.03, 0.5), V43)).toBe(false);
  });

  it("accounts for the cover-crop of a 16:9 camera", () => {
    // 16:9 -> only the middle 75% of the width is visible in the 4:3 preview, so a face at 0.85 of the
    // raw width is far outside what the person sees, while the same offset on a 4:3 camera is also outside.
    expect(faceInsideGuide(boxAt(V169, 0.5, 0.5), V169)).toBe(true);
    expect(faceInsideGuide(boxAt(V169, 0.85, 0.5), V169)).toBe(false);
    // Just inside the oval on screen: 0.5 + (0.20 * 0.75) of raw width.
    expect(faceInsideGuide(boxAt(V169, 0.5 + 0.2 * 0.75, 0.5), V169)).toBe(true);
  });

  it("never blocks when the video size is not known yet", () => {
    expect(faceInsideGuide({ x: 0, y: 0, width: 10, height: 10 }, { width: 0, height: 0 })).toBe(true);
  });
});
