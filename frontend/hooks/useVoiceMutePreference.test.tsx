// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useVoiceMutePreference } from "./useVoiceMutePreference";

const AIRA_KEY = "aira_voice_muted";
const OLD_ROYAL_KEY = "royal_hrms_voice_muted";

beforeEach(() => window.localStorage.clear());
afterEach(() => window.localStorage.clear());

describe("useVoiceMutePreference storage key", () => {
  it("defaults to unmuted", () => {
    const { result } = renderHook(() => useVoiceMutePreference());
    expect(result.current.isMuted).toBe(false);
  });

  it("persists the toggle under aira_voice_muted only", () => {
    const { result } = renderHook(() => useVoiceMutePreference());
    act(() => result.current.toggleMuted());
    expect(result.current.isMuted).toBe(true);
    expect(window.localStorage.getItem(AIRA_KEY)).toBe("1");
    expect(window.localStorage.getItem(OLD_ROYAL_KEY)).toBeNull();
    act(() => result.current.toggleMuted());
    expect(window.localStorage.getItem(AIRA_KEY)).toBeNull();
  });

  it("restores a saved aira_voice_muted preference after mount", () => {
    window.localStorage.setItem(AIRA_KEY, "1");
    const { result } = renderHook(() => useVoiceMutePreference());
    expect(result.current.isMuted).toBe(true);
  });

  it("never reads, migrates or writes the old Royal HRMS key", () => {
    window.localStorage.setItem(OLD_ROYAL_KEY, "1");
    const { result } = renderHook(() => useVoiceMutePreference());
    expect(result.current.isMuted).toBe(false); // the old value is ignored entirely
    act(() => result.current.toggleMuted());
    act(() => result.current.toggleMuted());
    expect(window.localStorage.getItem(OLD_ROYAL_KEY)).toBe("1"); // untouched: not removed, not migrated
    expect(window.localStorage.getItem(AIRA_KEY)).toBeNull();
  });
});
