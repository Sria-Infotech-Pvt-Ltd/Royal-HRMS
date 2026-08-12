// Plain-Node verification for clahe.ts — no test framework is set up in this
// frontend yet (no jest/vitest in package.json), so this is a runnable,
// assertion-based script rather than a framework test file. Run with:
//   npx tsx lib/faceApi/__tests__/clahe.verify.ts
// Exits non-zero (and prints which assertion failed) on any regression.
import { applyClahe, type PixelBuffer } from '../clahe';

let failures = 0;
function assert(condition: boolean, message: string): void {
  if (condition) {
    console.log(`  ok  - ${message}`);
  } else {
    failures += 1;
    console.error(`  FAIL - ${message}`);
  }
}

function makeBuffer(width: number, height: number, fill: (x: number, y: number) => number): PixelBuffer {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const v = fill(x, y);
      const p = (y * width + x) * 4;
      data[p] = v; data[p + 1] = v; data[p + 2] = v; data[p + 3] = 255;
    }
  }
  return { data, width, height };
}

function stddev(values: number[]): number {
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / values.length;
  return Math.sqrt(variance);
}

function luminanceValues(buffer: PixelBuffer): number[] {
  const out: number[] = [];
  for (let i = 0; i < buffer.width * buffer.height; i++) {
    const p = i * 4;
    out.push(0.299 * buffer.data[p] + 0.587 * buffer.data[p + 1] + 0.114 * buffer.data[p + 2]);
  }
  return out;
}

console.log('CLAHE: dark, low-contrast frame gets meaningfully more contrast');
{
  // Simulates a poorly-lit face capture: everything crammed into a narrow
  // dark range (40-70 out of 0-255) instead of using the full range.
  const buffer = makeBuffer(96, 96, (x, y) => 40 + ((x + y) % 30));
  const before = stddev(luminanceValues(buffer));
  applyClahe(buffer, { tileSize: 16, clipLimit: 3.0 });
  const after = stddev(luminanceValues(buffer));
  console.log(`    luminance stddev: before=${before.toFixed(2)} after=${after.toFixed(2)}`);
  assert(after > before * 1.5, 'contrast (luminance stddev) increases substantially after CLAHE');
  assert(
    buffer.data.every(v => v >= 0 && v <= 255),
    'all output bytes stay in valid [0,255] range',
  );
}

console.log('CLAHE: perfectly uniform frame stays sane (no NaN/crash, no artificial contrast invented)');
{
  const buffer = makeBuffer(64, 64, () => 128);
  applyClahe(buffer, { tileSize: 16, clipLimit: 3.0 });
  const values = luminanceValues(buffer);
  assert(values.every(v => Number.isFinite(v)), 'no NaN/Infinity produced');
  assert(stddev(values) < 5, 'a genuinely blank frame is not hallucinated into fake contrast');
}

console.log('CLAHE: local (regional) contrast improves, not just a global stretch');
{
  // Left half dark-and-flat, right half bright-and-flat — a global stretch
  // alone can't add contrast to either half individually; CLAHE (being
  // tiled) should still expose SOME internal structure once combined with
  // the per-tile fine detail below.
  const buffer = makeBuffer(64, 64, (x, y) => {
    const base = x < 32 ? 30 : 220;
    return base + ((x * 7 + y * 3) % 10); // small texture riding on each half's flat base
  });
  const beforeLeft = stddev(luminanceValues(buffer).filter((_, i) => (i % 64) < 32));
  applyClahe(buffer, { tileSize: 16, clipLimit: 3.0 });
  const afterLeft = stddev(luminanceValues(buffer).filter((_, i) => (i % 64) < 32));
  console.log(`    dark-half local stddev: before=${beforeLeft.toFixed(2)} after=${afterLeft.toFixed(2)}`);
  assert(afterLeft > beforeLeft, "the dark half's own internal texture gets more contrast, independent of the bright half");
}

console.log();
if (failures > 0) {
  console.error(`${failures} assertion(s) failed.`);
  process.exit(1);
} else {
  console.log('All CLAHE assertions passed.');
}
