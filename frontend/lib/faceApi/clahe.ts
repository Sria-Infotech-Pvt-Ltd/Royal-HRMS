// CLAHE (Contrast Limited Adaptive Histogram Equalization) for face
// registration capture — run on a video frame before handing it to
// face-api.js's detector/descriptor pipeline, so a registration captured in
// poor or uneven lighting doesn't become a permanent, low-margin reference
// embedding (see FaceVerificationService's threshold discussion — a
// registration whose OWN historical match distances already sit near
// FACE_MATCH_MAX_DISTANCE leaves almost no room to reject an impostor).
//
// Deliberately a real, from-scratch CLAHE — tiled histograms, per-tile clip
// limit, bilinear interpolation between tile mappings — not a global
// contrast stretch. A single global equalization would still let one dark
// corner of the frame (e.g. a shadowed side of the face) stay poorly
// exposed; CLAHE's whole point is normalizing lighting regionally.
//
// Operates on the LUMINANCE channel only (ITU-R BT.601 weights) and rescales
// R/G/B proportionally to the luminance change — this normalizes exposure
// and local contrast while preserving color, which matters here only
// insofar as it keeps the frame looking like a real photo for face-api.js's
// detector (trained on color images), not because color itself carries any
// identity signal this pipeline uses.
//
// Pure function over a plain pixel-buffer shape (not the DOM's ImageData
// type) so this is testable in plain Node — see faceApi tests, run via
// `npx tsx`, no browser/DOM required.

export interface PixelBuffer {
  /** RGBA, 4 bytes per pixel, row-major — same byte layout as CanvasRenderingContext2D's ImageData.data. */
  data: Uint8ClampedArray;
  width: number;
  height: number;
}

export interface ClaheOptions {
  /** Tile edge length in pixels. Smaller = more local adaptivity, but noisier
   *  at tile boundaries; larger = closer to a single global equalization. */
  tileSize?: number;
  /** Multiplier on each tile's "fair share" histogram count
   *  (tilePixelCount / 256) — bins above this get clipped and their excess
   *  redistributed evenly, which is what keeps CLAHE from over-amplifying
   *  noise in near-uniform regions (e.g. a smooth cheek) the way plain
   *  histogram equalization would. */
  clipLimit?: number;
}

const DEFAULT_TILE_SIZE = 32;
const DEFAULT_CLIP_LIMIT = 3.0;
const HISTOGRAM_BINS = 256;

const LUMA_R = 0.299;
const LUMA_G = 0.587;
const LUMA_B = 0.114;

interface TileGrid {
  tilesX: number;
  tilesY: number;
  tileSize: number;
  /** mappings[tileIndex] is a 256-entry lookup table: old luminance (0-255) -> new luminance (0-255). */
  mappings: Uint8ClampedArray[];
}

/**
 * Applies CLAHE to `buffer` in place and returns it (for chaining). Safe to
 * call on any RGBA buffer with width/height > 0; a degenerate 1x1 buffer
 * just maps through unchanged (nothing to equalize).
 */
export function applyClahe(buffer: PixelBuffer, options: ClaheOptions = {}): PixelBuffer {
  const tileSize = options.tileSize ?? DEFAULT_TILE_SIZE;
  const clipLimit = options.clipLimit ?? DEFAULT_CLIP_LIMIT;
  const { width, height, data } = buffer;
  if (width <= 0 || height <= 0) return buffer;

  const luminance = computeLuminance(data, width, height);
  const grid = buildTileMappings(luminance, width, height, tileSize, clipLimit);
  applyInterpolatedMappings(data, luminance, width, height, grid);
  return buffer;
}

function computeLuminance(data: Uint8ClampedArray, width: number, height: number): Float32Array {
  const luminance = new Float32Array(width * height);
  for (let i = 0, p = 0; i < luminance.length; i++, p += 4) {
    luminance[i] = LUMA_R * data[p] + LUMA_G * data[p + 1] + LUMA_B * data[p + 2];
  }
  return luminance;
}

function buildTileMappings(
  luminance: Float32Array, width: number, height: number, tileSize: number, clipLimit: number,
): TileGrid {
  const tilesX = Math.max(1, Math.ceil(width / tileSize));
  const tilesY = Math.max(1, Math.ceil(height / tileSize));
  const mappings: Uint8ClampedArray[] = new Array(tilesX * tilesY);

  for (let ty = 0; ty < tilesY; ty++) {
    for (let tx = 0; tx < tilesX; tx++) {
      const x0 = tx * tileSize;
      const y0 = ty * tileSize;
      const x1 = Math.min(x0 + tileSize, width);
      const y1 = Math.min(y0 + tileSize, height);
      mappings[ty * tilesX + tx] = buildTileMapping(luminance, width, x0, y0, x1, y1, clipLimit);
    }
  }
  return { tilesX, tilesY, tileSize, mappings };
}

/** Histogram -> clip -> redistribute -> CDF -> 0-255 lookup table, for one tile's pixels. */
function buildTileMapping(
  luminance: Float32Array, width: number, x0: number, y0: number, x1: number, y1: number, clipLimit: number,
): Uint8ClampedArray {
  const histogram = new Float64Array(HISTOGRAM_BINS);
  let pixelCount = 0;
  for (let y = y0; y < y1; y++) {
    const rowOffset = y * width;
    for (let x = x0; x < x1; x++) {
      const bin = Math.min(HISTOGRAM_BINS - 1, Math.max(0, Math.round(luminance[rowOffset + x])));
      histogram[bin] += 1;
      pixelCount += 1;
    }
  }
  if (pixelCount === 0) {
    // Degenerate (zero-area) tile — identity mapping.
    const identity = new Uint8ClampedArray(HISTOGRAM_BINS);
    for (let i = 0; i < HISTOGRAM_BINS; i++) identity[i] = i;
    return identity;
  }

  const clip = clipLimit * (pixelCount / HISTOGRAM_BINS);
  let excess = 0;
  for (let i = 0; i < HISTOGRAM_BINS; i++) {
    if (histogram[i] > clip) {
      excess += histogram[i] - clip;
      histogram[i] = clip;
    }
  }
  // Single-pass redistribution (the standard CLAHE approximation — a fully
  // iterative redistribute-then-reclip loop converges to almost the same
  // result for natural images and isn't worth the extra passes here).
  const redistribution = excess / HISTOGRAM_BINS;
  for (let i = 0; i < HISTOGRAM_BINS; i++) histogram[i] += redistribution;

  const mapping = new Uint8ClampedArray(HISTOGRAM_BINS);
  let cumulative = 0;
  for (let i = 0; i < HISTOGRAM_BINS; i++) {
    cumulative += histogram[i];
    mapping[i] = Math.round(((HISTOGRAM_BINS - 1) * cumulative) / pixelCount);
  }
  return mapping;
}

/**
 * The "adaptive" half of CLAHE: rather than applying one tile's mapping
 * uniformly across it (which would produce visible tile-edge seams), every
 * pixel blends the mappings of the 4 tiles whose CENTERS surround it,
 * weighted by how close it is to each center. A pixel exactly on a tile
 * center gets that tile's mapping undiluted; a pixel on a tile boundary
 * gets an even blend of its neighbors.
 */
function applyInterpolatedMappings(
  data: Uint8ClampedArray, luminance: Float32Array, width: number, height: number, grid: TileGrid,
): void {
  const { tilesX, tilesY, tileSize, mappings } = grid;

  for (let y = 0; y < height; y++) {
    // Continuous tile-space position, shifted so integer values land on
    // tile CENTERS rather than tile origins.
    const ty = y / tileSize - 0.5;
    const ty0 = clampInt(Math.floor(ty), 0, tilesY - 1);
    const ty1 = clampInt(ty0 + 1, 0, tilesY - 1);
    const wy = clamp01(ty - Math.floor(ty));

    for (let x = 0; x < width; x++) {
      const tx = x / tileSize - 0.5;
      const tx0 = clampInt(Math.floor(tx), 0, tilesX - 1);
      const tx1 = clampInt(tx0 + 1, 0, tilesX - 1);
      const wx = clamp01(tx - Math.floor(tx));

      const oldY = luminance[y * width + x];
      const bin = Math.min(HISTOGRAM_BINS - 1, Math.max(0, Math.round(oldY)));

      const m00 = mappings[ty0 * tilesX + tx0][bin];
      const m10 = mappings[ty0 * tilesX + tx1][bin];
      const m01 = mappings[ty1 * tilesX + tx0][bin];
      const m11 = mappings[ty1 * tilesX + tx1][bin];
      const top = m00 * (1 - wx) + m10 * wx;
      const bottom = m01 * (1 - wx) + m11 * wx;
      const newY = top * (1 - wy) + bottom * wy;

      const scale = oldY > 1 ? newY / oldY : 1;
      const p = (y * width + x) * 4;
      data[p] = clampByte(data[p] * scale);
      data[p + 1] = clampByte(data[p + 1] * scale);
      data[p + 2] = clampByte(data[p + 2] * scale);
      // alpha (data[p + 3]) untouched.
    }
  }
}

function clampInt(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}
function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}
function clampByte(v: number): number {
  return Math.min(255, Math.max(0, Math.round(v)));
}
