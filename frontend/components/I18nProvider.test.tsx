// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import I18nProvider from "@/components/I18nProvider";
import LoginLanguageSwitch from "@/components/auth/LoginLanguageSwitch";
import { useT } from "@/hooks/useI18n";
import { LANGUAGE_STORAGE_KEY } from "@/lib/i18n/languages";

function Greeting() {
  const t = useT();
  return <p>{t("Welcome back")}</p>;
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

  it("switches the whole screen when a language is chosen, and remembers it", () => {
    render(<I18nProvider><Greeting /><LoginLanguageSwitch /></I18nProvider>);
    fireEvent.click(screen.getByRole("button", { name: "हिन्दी" }));
    expect(screen.getByText("वापसी पर स्वागत है")).toBeTruthy();
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("hi");
    expect(document.documentElement.lang).toBe("hi");
    fireEvent.click(screen.getByRole("button", { name: "తెలుగు" }));
    expect(screen.getByText("తిరిగి స్వాగతం")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "English" }));
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
});
