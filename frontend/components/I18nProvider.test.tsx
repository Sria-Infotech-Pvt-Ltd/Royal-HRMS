// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import I18nProvider from "@/components/I18nProvider";
import LoginLanguageSwitch from "@/components/auth/LoginLanguageSwitch";
import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";
import { LANGUAGE_STORAGE_KEY } from "@/lib/i18n/languages";

function Greeting() {
  const t = useT();
  return <p>{t("Welcome back")}</p>;
}

// A screen that uses the plain tr() function and never subscribes to the language (most converted screens).
function PlainGreeting() {
  return <p>{tr("Welcome back")}</p>;
}

beforeEach(() => { localStorage.clear(); document.documentElement.lang = ""; });
afterEach(cleanup);

describe("I18nProvider", () => {
  it("reads in English with nothing chosen, and without a provider at all", () => {
    render(<Greeting />);
    expect(screen.getByText("Welcome back")).toBeTruthy();
    cleanup();
    render(<I18nProvider><Greeting /></I18nProvider>);
    expect(screen.getByText("Welcome back")).toBeTruthy();
  });

// The trigger's own label is translated too, so it is found by what it does (it opens a dialog), not by its name.
function pickLanguage(nativeName: RegExp) {
  fireEvent.click(screen.getAllByRole("button").find(button => button.getAttribute("aria-haspopup") === "dialog") as HTMLElement);
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: nativeName }));
}

  it("switches the whole screen when a language is chosen, and remembers it", () => {
    render(<I18nProvider><Greeting /><LoginLanguageSwitch /></I18nProvider>);
    pickLanguage(/हिन्दी/);
    expect(screen.getByText("वापसी पर स्वागत है")).toBeTruthy();
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("hi");
    expect(document.documentElement.lang).toBe("hi");
    pickLanguage(/తెలుగు/);
    expect(screen.getByText("తిరిగి స్వాగతం")).toBeTruthy();
    pickLanguage(/English/);
    expect(screen.getByText("Welcome back")).toBeTruthy();
  });

  it("starts in the language saved in this browser", () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "te");
    render(<I18nProvider><Greeting /></I18nProvider>);
    expect(screen.getByText("తిరిగి స్వాగతం")).toBeTruthy();
  });

  it("ignores a saved value it does not know", () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "klingon");
    render(<I18nProvider><Greeting /></I18nProvider>);
    expect(screen.getByText("Welcome back")).toBeTruthy();
  });

  it("also switches screens that use the plain tr() function", () => {
    render(<I18nProvider><PlainGreeting /><LoginLanguageSwitch /></I18nProvider>);
    expect(screen.getByText("Welcome back")).toBeTruthy();
    pickLanguage(/हिन्दी/);
    expect(screen.getByText("वापसी पर स्वागत है")).toBeTruthy();
    pickLanguage(/English/);
    expect(screen.getByText("Welcome back")).toBeTruthy();
  });

  it("lists all 13 languages, finds one by its English or native name, and closes on Escape", () => {
    render(<I18nProvider><LoginLanguageSwitch /></I18nProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Language" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getAllByRole("button")).toHaveLength(13);
    fireEvent.change(within(dialog).getByRole("searchbox"), { target: { value: "tam" } });
    expect(within(dialog).getAllByRole("button").map(button => button.getAttribute("lang"))).toEqual(["ta"]);
    fireEvent.change(within(dialog).getByRole("searchbox"), { target: { value: "zzz" } });
    expect(within(dialog).getByRole("status").textContent).toContain("No language matches that.");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
