import { defineConfig } from "vitest/config";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Minimal Vitest setup (Phase 4 — voice-commands TTS work) — this repo has
// no test infrastructure of its own to match, so this mirrors the one path
// alias (@/*) tsconfig.json already defines rather than inventing new
// conventions. "node" environment is enough for the lib-level network/logic
// tests this phase adds; a jsdom environment can be layered on per-test
// (via a `// @vitest-environment jsdom` docblock) if a future test needs
// real DOM/Audio globals.
export default defineConfig({
  test: {
    environment: "node",
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
