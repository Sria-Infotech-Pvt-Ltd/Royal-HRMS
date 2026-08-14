// Plain-Node verification for qualityGate.ts. Run with:
//   npx tsx lib/faceApi/__tests__/qualityGate.verify.ts
import {
  assessFrameQuality, computeFrontality, assessCaptureConsistency,
  averageDescriptors, euclideanDistance, QUALITY_THRESHOLDS,
  type FrameQualityMetrics,
} from '../qualityGate';

let failures = 0;
function assert(condition: boolean, message: string): void {
  if (condition) console.log(`  ok  - ${message}`);
  else { failures += 1; console.error(`  FAIL - ${message}`); }
}

const GOOD_METRICS: FrameQualityMetrics = {
  detectionScore: 0.95, faceWidthRatio: 0.4, frontality: 0.95, meanLuminance: 130,
};

console.log('assessFrameQuality: a clean frame passes with no reasons');
{
  const result = assessFrameQuality(GOOD_METRICS);
  assert(result.passed, 'good metrics pass the gate');
  assert(result.reasons.length === 0, 'no rejection reasons on a passing frame');
}

console.log('assessFrameQuality: each individual failure mode is caught on its own');
{
  const cases: Array<[Partial<FrameQualityMetrics>, string]> = [
    [{ detectionScore: 0.5 }, 'low detector confidence'],
    [{ faceWidthRatio: 0.05 }, 'face too far'],
    [{ faceWidthRatio: 0.9 }, 'face too close'],
    [{ frontality: 0.3 }, 'head turned away'],
    [{ meanLuminance: 20 }, 'too dark'],
    [{ meanLuminance: 250 }, 'too bright'],
  ];
  for (const [override, label] of cases) {
    const result = assessFrameQuality({ ...GOOD_METRICS, ...override });
    assert(!result.passed, `${label} -> rejected`);
    assert(result.reasons.length === 1, `${label} -> exactly one reason (${result.reasons[0]})`);
  }
}

console.log('computeFrontality: symmetric landmarks score near 1, a turned head scores lower');
{
  const leftEye = [{ x: 30, y: 40 }];
  const rightEye = [{ x: 70, y: 40 }];
  const frontalNose = { x: 50, y: 60 }; // equidistant from both eye centers
  const turnedNose = { x: 65, y: 60 };  // shifted toward the right eye — a head turn

  const frontalScore = computeFrontality(leftEye, rightEye, frontalNose);
  const turnedScore = computeFrontality(leftEye, rightEye, turnedNose);
  console.log(`    frontal=${frontalScore.toFixed(3)} turned=${turnedScore.toFixed(3)}`);
  assert(frontalScore > QUALITY_THRESHOLDS.MIN_FRONTALITY, 'a symmetric (frontal) face clears the threshold');
  assert(turnedScore < frontalScore, 'a turned head scores measurably lower than frontal');
}

// ─── The core justification for multi-frame capture (item 3) ──────────────
// Simulate a "true" 128-d descriptor (stand-in for one real person's actual
// face-api.js output) plus per-frame capture noise (stand-in for the kind of
// frame-to-frame variation a real webcam session has: micro-movements,
// slightly different lighting/angle each frame). This demonstrates the
// MATHEMATICAL reason averaging multiple frames should tighten a reference
// embedding — it is NOT a claim about real face-api.js numbers, which can
// only come from an actual browser capture (see the accompanying report).
console.log();
console.log('averageDescriptors: averaging N noisy frames lands closer to the true descriptor than a single frame does');
{
  const DIMENSIONS = 128;
  const trueDescriptor = Array.from({ length: DIMENSIONS }, (_, i) => Math.sin(i) * 0.1);

  function noisyFrame(noiseScale: number): number[] {
    return trueDescriptor.map(v => v + (Math.random() - 0.5) * 2 * noiseScale);
  }

  // Deterministic-ish comparison: average over many trials so this isn't
  // sensitive to one lucky/unlucky Math.random() draw.
  const TRIALS = 200;
  const FRAMES_PER_TRIAL = 4;
  const NOISE_SCALE = 0.05; // roughly the kind of frame-to-frame jitter real capture noise might look like

  let singleFrameTotal = 0;
  let averagedTotal = 0;
  for (let t = 0; t < TRIALS; t++) {
    const frames = Array.from({ length: FRAMES_PER_TRIAL }, () => noisyFrame(NOISE_SCALE));
    singleFrameTotal += euclideanDistance(frames[0], trueDescriptor); // "one bad/lucky frame becomes the reference" — today's behavior
    averagedTotal += euclideanDistance(averageDescriptors(frames), trueDescriptor);
  }
  const meanSingleFrameError = singleFrameTotal / TRIALS;
  const meanAveragedError = averagedTotal / TRIALS;
  console.log(`    mean distance-to-truth: single frame=${meanSingleFrameError.toFixed(4)} averaged(${FRAMES_PER_TRIAL} frames)=${meanAveragedError.toFixed(4)}`);
  console.log(`    improvement: ${(100 * (1 - meanAveragedError / meanSingleFrameError)).toFixed(1)}% tighter`);
  assert(meanAveragedError < meanSingleFrameError, 'averaging multiple frames is closer to the true descriptor, on average, than trusting any one frame');
}

console.log();
console.log('assessCaptureConsistency: catches a genuinely inconsistent capture session (e.g. person moved mid-capture)');
{
  const DIMENSIONS = 128;
  const trueDescriptor = Array.from({ length: DIMENSIONS }, (_, i) => Math.sin(i) * 0.1);
  const consistentFrames = Array.from({ length: 4 }, () =>
    trueDescriptor.map(v => v + (Math.random() - 0.5) * 2 * 0.03));
  // One frame captured after the person turned/moved — a much larger jump.
  const inconsistentFrames = [
    ...consistentFrames.slice(0, 3),
    trueDescriptor.map(v => v + (Math.random() - 0.5) * 2 * 0.03 + 0.4),
  ];

  const MAX_ALLOWED = 0.35; // same shape of constant multiFrameCapture.ts will use
  const consistentResult = assessCaptureConsistency(consistentFrames, MAX_ALLOWED);
  const inconsistentResult = assessCaptureConsistency(inconsistentFrames, MAX_ALLOWED);
  console.log(`    consistent set:   mean=${consistentResult.meanPairwiseDistance.toFixed(4)} max=${consistentResult.maxPairwiseDistance.toFixed(4)} passed=${consistentResult.passed}`);
  console.log(`    inconsistent set: mean=${inconsistentResult.meanPairwiseDistance.toFixed(4)} max=${inconsistentResult.maxPairwiseDistance.toFixed(4)} passed=${inconsistentResult.passed}`);
  assert(consistentResult.passed, 'a genuinely consistent capture session passes');
  assert(!inconsistentResult.passed, 'a session with one outlier frame is caught, not silently averaged in');
}

console.log();
if (failures > 0) {
  console.error(`${failures} assertion(s) failed.`);
  process.exit(1);
} else {
  console.log('All qualityGate assertions passed.');
}
