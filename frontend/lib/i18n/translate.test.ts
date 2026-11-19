import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
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

// Every English text passed to t("...") / tr("...") anywhere in the app must have a Hindi and a Telugu wording, so a screen that was
// converted can never ship half translated. Text built from variables cannot be looked up: use a {placeholder} instead.
function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap(name => {
    if (name === "node_modules" || name === ".next" || name === "messages") return [];
    const full = path.join(directory, name);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) ? [full] : [];
  });
}

describe("translated screens", () => {
  const CALL = /\b(?:tr|t)\(\s*(?:[^"()]*?\?\s*)?"((?:[^"\\]|\\.)*)"(?:\s*:\s*"((?:[^"\\]|\\.)*)")?/g;

  it("have a wording in every language for each text they translate", () => {
    const root = path.resolve(__dirname, "../..");
    const missing: string[] = [];
    for (const directory of ["app", "components", "hooks", "lib"]) {
      for (const file of sourceFiles(path.join(root, directory))) {
        for (const match of readFileSync(file, "utf8").matchAll(CALL)) {
          for (const literal of [match[1], match[2]]) {
            if (!literal) continue;
            const english = JSON.parse(`"${literal}"`) as string;
            for (const code of Object.keys(MESSAGES) as (keyof typeof MESSAGES)[]) {
              if (!(english in MESSAGES[code])) missing.push(`${code}: "${english}" (${path.relative(root, file)})`);
            }
          }
        }
      }
    }
    expect(missing).toEqual([]);
  });
});
