import { describe, expect, it } from "vitest";
import { fitWithin, shouldShrink, shrinkImageForUpload, smallestWithinTarget, SHRINK_ABOVE_BYTES } from "./shrinkImage";

const fileOf = (type: string, size: number, name = "scan.png") => new File([new Uint8Array(size)], name, { type });

describe("fitWithin", () => {
  it("caps the long side and keeps the shape", () => {
    expect(fitWithin(4000, 3000)).toEqual({ width: 1600, height: 1200 });
    expect(fitWithin(3000, 4000)).toEqual({ width: 1200, height: 1600 });
  });
  it("never enlarges a smaller image", () => {
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 });
    expect(fitWithin(1600, 1600)).toEqual({ width: 1600, height: 1600 });
  });
  it("never produces a zero side for a very thin image", () => {
    expect(fitWithin(10000, 1)).toEqual({ width: 1600, height: 1 });
  });
});

describe("shouldShrink", () => {
  it("shrinks only big JPEG and PNG files", () => {
    expect(shouldShrink({ type: "image/jpeg", size: SHRINK_ABOVE_BYTES + 1 })).toBe(true);
    expect(shouldShrink({ type: "image/png", size: 2_000_000 })).toBe(true);
    expect(shouldShrink({ type: "image/jpeg", size: SHRINK_ABOVE_BYTES })).toBe(false);
    expect(shouldShrink({ type: "application/pdf", size: 4_000_000 })).toBe(false);
  });
});

describe("smallestWithinTarget", () => {
  const blobOfSize = (size: number) => new Blob([new Uint8Array(size)]);

  it("stops at the first step that is small enough", async () => {
    const tried: number[] = [];
    const result = await smallestWithinTarget(async side => { tried.push(side); return blobOfSize(side === 1400 ? 200_000 : 50_000); }, 70_000);
    expect(tried).toEqual([1400, 1200]);
    expect(result?.size).toBe(50_000);
  });

  it("returns the smallest result when no step reaches the target", async () => {
    const sizes: Record<number, number> = { 1400: 300_000, 1200: 150_000, 1000: 120_000 };
    const result = await smallestWithinTarget(async side => blobOfSize(sizes[side]), 70_000);
    expect(result?.size).toBe(120_000);
  });

  it("returns null when nothing could be produced", async () => {
    expect(await smallestWithinTarget(async () => null)).toBeNull();
  });
});

describe("shrinkImageForUpload", () => {
  it("hands back the very same file for a PDF and for a small image", async () => {
    const pdf = fileOf("application/pdf", 3_000_000, "offer.pdf");
    const small = fileOf("image/png", 1000);
    expect(await shrinkImageForUpload(pdf)).toBe(pdf);
    expect(await shrinkImageForUpload(small)).toBe(small);
  });
  it("hands back the original when the image cannot be decoded (the server judges it as before)", async () => {
    const broken = fileOf("image/jpeg", 900_000, "broken.jpg");
    expect(await shrinkImageForUpload(broken)).toBe(broken);
  });
});
