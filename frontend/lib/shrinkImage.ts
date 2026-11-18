// Shrinks a photo in the browser before it is uploaded. A phone photo is 1 to 5 MB, and on a slow office line (a measured
// 0.2 Mbit/s upload) 2 MB took over a minute and the server gave up at 60 seconds. The target here is about 70 KB, which is
// roughly 2 seconds on that line: a scanned ID or certificate is still readable at 1000 to 1400 pixels. Each step down in the
// ladder is tried only when the one before it was still too big. PDFs and anything that cannot be shrunk are returned exactly as
// they came, so this can never make an upload fail that would otherwise have worked.

export const TARGET_BYTES = 70 * 1024;
export const SHRINK_ABOVE_BYTES = TARGET_BYTES;
export const MAX_LONG_SIDE_PX = 1600;
const SHRINKABLE_TYPES = new Set(["image/jpeg", "image/png"]);

/** From best quality to smallest: the long side in pixels and the JPEG quality. The last step is the floor for readability. */
export const SHRINK_LADDER: ReadonlyArray<{ side: number; quality: number }> = [
  { side: 1400, quality: 0.75 }, { side: 1200, quality: 0.65 }, { side: 1000, quality: 0.55 },
];

/** The size to draw at: the long side is capped at `maxSide`, the shape is kept, and a smaller image is never enlarged. */
export function fitWithin(width: number, height: number, maxSide: number = MAX_LONG_SIDE_PX): { width: number; height: number } {
  const longSide = Math.max(width, height);
  if (longSide <= maxSide) return { width, height };
  const scale = maxSide / longSide;
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

export function shouldShrink(file: Pick<File, "type" | "size">): boolean {
  return SHRINKABLE_TYPES.has(file.type) && file.size > SHRINK_ABOVE_BYTES;
}

/** Walks the ladder and returns the first result at or under the target, otherwise the smallest one produced (null if none). */
export async function smallestWithinTarget(
  encode: (side: number, quality: number) => Promise<Blob | null>,
  targetBytes: number = TARGET_BYTES,
): Promise<Blob | null> {
  let best: Blob | null = null;
  for (const { side, quality } of SHRINK_LADDER) {
    const blob = await encode(side, quality);
    if (blob && (best === null || blob.size < best.size)) best = blob;
    if (best && best.size <= targetBytes) break;
  }
  return best;
}

function jpegName(original: string): string {
  return original.replace(/\.[^./\\]+$/, "") + ".jpg";
}

/** A smaller JPEG copy of the photo, or the original file when it is not worth (or not possible) to shrink it. */
export async function shrinkImageForUpload(file: File): Promise<File> {
  if (!shouldShrink(file) || typeof createImageBitmap !== "function") return file;
  try {
    const bitmap = await createImageBitmap(file);
    const encode = (side: number, quality: number) => {
      const { width, height } = fitWithin(bitmap.width, bitmap.height, side);
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) return Promise.resolve<Blob | null>(null);
      context.fillStyle = "#ffffff";   // a PNG with a transparent background would otherwise turn black as a JPEG
      context.fillRect(0, 0, width, height);
      context.drawImage(bitmap, 0, 0, width, height);
      return new Promise<Blob | null>(resolve => canvas.toBlob(resolve, "image/jpeg", quality));
    };
    const blob = await smallestWithinTarget(encode);
    bitmap.close();
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], jpegName(file.name), { type: "image/jpeg", lastModified: file.lastModified });
  } catch {
    return file;   // an unreadable image is left for the server to judge, exactly as before
  }
}
