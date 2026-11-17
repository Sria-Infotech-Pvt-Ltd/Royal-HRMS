// @vitest-environment jsdom
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FaceModelPreloader, { START_DELAY_MS } from "./FaceModelPreloader";

const loadFaceApiModels = vi.fn(() => Promise.resolve());
let isMandatory = true;
vi.mock("@/lib/faceApi/loadModels", () => ({ loadFaceApiModels: () => loadFaceApiModels() }));
vi.mock("@/hooks/useFaceVerificationStatus", () => ({ useFaceVerificationStatus: () => ({ isMandatory }) }));

beforeEach(() => {
  vi.useFakeTimers();
  loadFaceApiModels.mockClear();
  isMandatory = true;
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("FaceModelPreloader", () => {
  it("does not start the ~7 MB download until the page has loaded and a few seconds have passed", () => {
    render(<FaceModelPreloader />);   // jsdom reports the document as already loaded
    act(() => { vi.advanceTimersByTime(START_DELAY_MS - 1); });
    expect(loadFaceApiModels).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(START_DELAY_MS + 3500); });
    expect(loadFaceApiModels).toHaveBeenCalledTimes(1);
  });

  it("never downloads when the organisation has face verification off", () => {
    isMandatory = false;
    render(<FaceModelPreloader />);
    act(() => { vi.advanceTimersByTime(60_000); });
    expect(loadFaceApiModels).not.toHaveBeenCalled();
  });

  it("cancels the download if the user leaves before it starts", () => {
    const view = render(<FaceModelPreloader />);
    view.unmount();
    act(() => { vi.advanceTimersByTime(60_000); });
    expect(loadFaceApiModels).not.toHaveBeenCalled();
  });
});
