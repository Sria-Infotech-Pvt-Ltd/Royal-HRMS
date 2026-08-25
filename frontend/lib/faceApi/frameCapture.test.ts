import { describe, expect, it } from "vitest";
import { assessEyeOcclusion } from "./frameCapture";

// Synthetic RGBA buffers — no browser/canvas needed, same "plain function
// over pixel data" testability clahe.ts and qualityGate.ts already have.
// Layout: a flat mid-gray background with two eye-shaped regions painted in,
// one per eye, at fixed pixel coordinates the landmark points below point at.
const WIDTH = 20;
const HEIGHT = 10;
const BACKGROUND_LUMINANCE = 130;

const LEFT_EYE_POINTS = [
  { x: 2, y: 4 }, { x: 3, y: 2 }, { x: 6, y: 2 }, { x: 8, y: 4 }, { x: 6, y: 6 }, { x: 3, y: 6 },
];
const RIGHT_EYE_POINTS = [
  { x: 11, y: 4 }, { x: 12, y: 2 }, { x: 15, y: 2 }, { x: 17, y: 4 }, { x: 15, y: 6 }, { x: 12, y: 6 },
];

function makeBuffer(): { data: Uint8ClampedArray; width: number; height: number } {
  const data = new Uint8ClampedArray(WIDTH * HEIGHT * 4);
  for (let i = 0; i < WIDTH * HEIGHT; i++) {
    const p = i * 4;
    data[p] = data[p + 1] = data[p + 2] = BACKGROUND_LUMINANCE;
    data[p + 3] = 255;
  }
  return { data, width: WIDTH, height: HEIGHT };
}

/** Paints every pixel within [x0,x1) x [y0,y1) to a single flat luminance —
 *  simulates a uniform dark lens over an eye. */
function paintFlat(buffer: { data: Uint8ClampedArray; width: number }, x0: number, y0: number, x1: number, y1: number, value: number): void {
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      const p = (y * buffer.width + x) * 4;
      buffer.data[p] = buffer.data[p + 1] = buffer.data[p + 2] = value;
    }
  }
}

/** Alternates two luminance values in a checkerboard — simulates a real open
 *  eye's internal contrast (sclera/iris/lash), which a flat lens lacks. */
function paintCheckerboard(buffer: { data: Uint8ClampedArray; width: number }, x0: number, y0: number, x1: number, y1: number, low: number, high: number): void {
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      const p = (y * buffer.width + x) * 4;
      const value = (x + y) % 2 === 0 ? low : high;
      buffer.data[p] = buffer.data[p + 1] = buffer.data[p + 2] = value;
    }
  }
}

describe("assessEyeOcclusion", () => {
  it("does not suspect occlusion for two clearly visible, well-lit, high-contrast eyes", () => {
    const buffer = makeBuffer();
    paintCheckerboard(buffer, 2, 2, 8, 6, 60, 220);
    paintCheckerboard(buffer, 11, 2, 17, 6, 60, 220);

    const result = assessEyeOcclusion(buffer, LEFT_EYE_POINTS, RIGHT_EYE_POINTS);

    expect(result.suspected).toBe(false);
    expect(result.left.mean).toBeGreaterThan(50);
    expect(result.right.mean).toBeGreaterThan(50);
  });

  it("suspects occlusion when both eye regions are uniformly dark and flat (simulated sunglasses)", () => {
    const buffer = makeBuffer();
    paintFlat(buffer, 2, 2, 8, 6, 25);
    paintFlat(buffer, 11, 2, 17, 6, 25);

    const result = assessEyeOcclusion(buffer, LEFT_EYE_POINTS, RIGHT_EYE_POINTS);

    expect(result.suspected).toBe(true);
    expect(result.left.mean).toBeLessThan(50);
    expect(result.left.stdDev).toBeLessThan(10);
    expect(result.right.mean).toBeLessThan(50);
    expect(result.right.stdDev).toBeLessThan(10);
  });

  it("does not trip when only one eye reads as dark and flat (asymmetric shadow/hair, not a real obstruction)", () => {
    const buffer = makeBuffer();
    paintFlat(buffer, 2, 2, 8, 6, 25); // left: dark and flat
    paintCheckerboard(buffer, 11, 2, 17, 6, 60, 220); // right: clearly a visible eye

    const result = assessEyeOcclusion(buffer, LEFT_EYE_POINTS, RIGHT_EYE_POINTS);

    expect(result.suspected).toBe(false);
  });

  it("does not trip on a dim room with real eye contrast still visible (dark but not flat)", () => {
    const buffer = makeBuffer();
    // Dim, but the checkerboard keeps stdDev well above the flatness floor.
    paintCheckerboard(buffer, 2, 2, 8, 6, 20, 45);
    paintCheckerboard(buffer, 11, 2, 17, 6, 20, 45);

    const result = assessEyeOcclusion(buffer, LEFT_EYE_POINTS, RIGHT_EYE_POINTS);

    expect(result.suspected).toBe(false);
  });

  it("does not trip on a uniformly bright-but-flat region (flat but not dark)", () => {
    const buffer = makeBuffer();
    paintFlat(buffer, 2, 2, 8, 6, 180);
    paintFlat(buffer, 11, 2, 17, 6, 180);

    const result = assessEyeOcclusion(buffer, LEFT_EYE_POINTS, RIGHT_EYE_POINTS);

    expect(result.suspected).toBe(false);
  });
});
