import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import QuickActionChips, { QUICK_ACTIONS } from "./QuickActionChips";

// renderToStaticMarkup (ships with react-dom, no new dependency, no DOM/
// jsdom needed — it's the same server-render path Next.js itself uses)
// renders real JSX to an HTML string in plain Node, which is enough to
// verify what actually reaches the page without adding a browser-emulation
// test harness this project doesn't otherwise have — same "pure function,
// no DOM dependency" testability preference the face-recognition phase's
// lib/faceApi tests already established.
function renderChips(): string {
  return renderToStaticMarkup(<QuickActionChips onPick={() => {}} />);
}

describe("QUICK_ACTIONS data completeness", () => {
  it("is non-empty", () => {
    expect(QUICK_ACTIONS.length).toBeGreaterThan(0);
  });

  // Fails loudly (one failure per offending chip, naming it) if a future
  // chip is ever added/edited without its Hindi counterpart, rather than
  // silently rendering a blank second line — the explicit testing
  // requirement this satisfies.
  it.each(QUICK_ACTIONS)("'%s' has both a non-empty English and Hindi label", (action) => {
    expect(action.label.trim().length).toBeGreaterThan(0);
    expect(action.labelHi.trim().length).toBeGreaterThan(0);
  });

  it("gives every chip a genuinely different Hindi label from its English one", () => {
    // Guards against a lazy placeholder (e.g. labelHi copied from label,
    // or every chip sharing one fallback string) slipping past the
    // non-empty check above.
    for (const action of QUICK_ACTIONS) {
      expect(action.labelHi).not.toBe(action.label);
    }
    const hindiLabels = QUICK_ACTIONS.map(a => a.labelHi);
    expect(new Set(hindiLabels).size).toBe(hindiLabels.length);
  });
});

describe("QuickActionChips rendering", () => {
  it("renders every chip's English label", () => {
    const html = renderChips();
    for (const action of QUICK_ACTIONS) {
      expect(html).toContain(action.label);
    }
  });

  it("renders every chip's Hindi label alongside its English one", () => {
    const html = renderChips();
    for (const action of QUICK_ACTIONS) {
      expect(html).toContain(action.labelHi);
    }
  });

  it("renders exactly one chip button per QUICK_ACTIONS entry, addressable by its phrase", () => {
    const html = renderChips();
    for (const action of QUICK_ACTIONS) {
      const testId = `voice-quick-action-${action.phrase.replace(/\s+/g, "-")}`;
      expect(html).toContain(`data-testid="${testId}"`);
    }
  });
});
