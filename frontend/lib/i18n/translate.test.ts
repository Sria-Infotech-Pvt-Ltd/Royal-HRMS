import { describe, expect, it } from "vitest";
import { ALL_NAV, isSection, TEAM_DASHBOARD_NAV_ITEM } from "@/lib/navConfig";
import { STATUS_TABS } from "@/app/dashboard/attendance/_components/attendanceView";
import { ACCENT_LABELS, MODE_LABELS } from "@/lib/theme";
import { LANGUAGES } from "./languages";
import { fillParams, MESSAGES, translate } from "./translate";

const PLACEHOLDER = /\{(\w+)\}/g;
function placeholders(text: string): string[] {
  return [...text.matchAll(PLACEHOLDER)].map(match => match[1]).sort();
}

describe("translate", () => {
  it("returns the English text for English", () => {
    expect(translate("en", "Sign in")).toBe("Sign in");
  });

  it("returns the wording of the chosen language", () => {
    expect(translate("hi", "Sign in")).toBe("साइन इन करें");
    expect(translate("te", "Sign in")).toBe("సైన్ ఇన్");
  });

  it("leaves text that has no translation yet in English", () => {
    expect(translate("hi", "A sentence nobody has translated")).toBe("A sentence nobody has translated");
  });

  it("fills placeholders after translating, and leaves unknown ones alone", () => {
    expect(translate("hi", "Sign in to your {brand} account", { brand: "AIRA" })).toBe("अपने AIRA खाते में साइन इन करें");
    expect(fillParams("Hello {name} {other}", { name: "Asha" })).toBe("Hello Asha {other}");
  });
});

describe("language files", () => {
  const codes = Object.keys(MESSAGES) as (keyof typeof MESSAGES)[];

  it("covers every language the picker offers (English is the source text)", () => {
    expect([...codes].sort()).toEqual(LANGUAGES.filter(code => code !== "en").sort());
  });

  it("has the same texts in every language, so no screen is half translated in one of them", () => {
    const [first, ...others] = codes;
    for (const other of others) {
      expect(Object.keys(MESSAGES[other]).sort(), `${other} vs ${first}`).toEqual(Object.keys(MESSAGES[first]).sort());
    }
  });

  it("never has an empty wording, and keeps the same {placeholders} as the English text", () => {
    for (const code of codes) {
      for (const [english, wording] of Object.entries(MESSAGES[code])) {
        expect(wording.trim(), `${code}: "${english}"`).not.toBe("");
        expect(placeholders(wording), `${code}: "${english}"`).toEqual(placeholders(english));
      }
    }
  });

  it("translates every navigation page and section name", () => {
    const names = new Set<string>([TEAM_DASHBOARD_NAV_ITEM.label, "Manager Dashboard"]);
    for (const entry of ALL_NAV) {
      if (isSection(entry)) names.add(entry.section);
      else { names.add(entry.label); if (entry.topNavLabel) names.add(entry.topNavLabel); }
    }
    for (const code of codes) {
      const missing = [...names].filter(name => !(name in MESSAGES[code]));
      expect(missing, `${code} is missing navigation names`).toEqual([]);
    }
  });

  it("translates the attendance filter tabs and the theme names", () => {
    const names = [...STATUS_TABS.map(tab => tab.label), ...Object.values(MODE_LABELS), ...Object.values(ACCENT_LABELS).map(entry => entry.label)];
    for (const code of codes) {
      expect(names.filter(name => !(name in MESSAGES[code])), `${code} is missing names`).toEqual([]);
    }
  });
});
