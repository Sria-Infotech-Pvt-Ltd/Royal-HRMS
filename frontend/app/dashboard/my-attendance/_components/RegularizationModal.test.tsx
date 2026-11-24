// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";

const post = vi.fn();
const showToast = vi.fn();
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));

import RegularizationModal from "./RegularizationModal";

beforeEach(() => { post.mockReset().mockResolvedValue({ data: { message: "ok" } }); showToast.mockReset(); });
afterEach(() => cleanup());


const select = () => (document.querySelector("select") as HTMLSelectElement);
const submit = () => fireEvent.submit(document.getElementById("regularization-form") as HTMLFormElement);

describe("RegularizationModal", () => {
  it("opens with nothing chosen and no times filled in", () => {
    render(<RegularizationModal onClose={vi.fn()} date="2026-11-18" />);
    expect(select().value).toBe("");
    expect(document.querySelectorAll('input[type="time"]').length).toBe(0);
  });

  it("will not submit until the person says which punch was missed", () => {
    render(<RegularizationModal onClose={vi.fn()} date="2026-11-18" />);
    submit();
    expect(post).not.toHaveBeenCalled();
    expect(showToast).toHaveBeenCalledWith("Choose which punch was missed.", "error");
  });

  it("a missed clock-out sends only the punch-out time the person typed", async () => {
    const onSuccess = vi.fn();
    render(<RegularizationModal onClose={vi.fn()} onSuccess={onSuccess} date="2026-11-18" />);
    fireEvent.change(select(), { target: { value: "OUT" } });
    expect(document.querySelectorAll('input[type="time"]').length).toBe(1);
    fireEvent.change(document.querySelector('input[type="time"]') as HTMLInputElement, { target: { value: "19:20" } });
    submit();
    await waitFor(() => expect(post).toHaveBeenCalled());
    const [url, body] = post.mock.calls[0];
    expect(url).toBe(API.attendance.correction);
    expect(body).toMatchObject({ date: "2026-11-18", punch_type: "OUT", correct_out_time: "19:20" });
    expect(body).not.toHaveProperty("correct_in_time");
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it("both shows both times, empty to start", () => {
    render(<RegularizationModal onClose={vi.fn()} date="2026-11-18" />);
    fireEvent.change(select(), { target: { value: "BOTH" } });
    const times = Array.from(document.querySelectorAll('input[type="time"]')) as HTMLInputElement[];
    expect(times.map(input => input.value)).toEqual(["", ""]);
  });
});
