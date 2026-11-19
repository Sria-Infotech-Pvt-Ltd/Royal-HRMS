// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import type { WorkFromHomeRequest } from "@/types/workFromHome";

const post = vi.fn();
const showToast = vi.fn();
let isConfirmed = true;
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("@/components/DialogProvider", () => ({ confirmDialog: () => Promise.resolve(isConfirmed) }));

import WfhLocationPolicy from "./WfhLocationPolicy";

const base = {
  id: "r1", status: "approved", employee_name: "Guru", location_label: "Home, Kondapur", enforce_location: true, can_set_location_policy: true,
} as WorkFromHomeRequest;

beforeEach(() => { post.mockReset(); showToast.mockReset(); isConfirmed = true; });
afterEach(() => cleanup());

const toggle = () => screen.getByText("Allow punching from any location").closest("label")!.querySelector("span") as HTMLElement;

describe("WfhLocationPolicy", () => {
  it("says punches must be near the declared location and offers the switch to an approver", () => {
    render(<WfhLocationPolicy request={base} />);
    expect(screen.getByText("Punches must be near Home, Kondapur.")).toBeTruthy();
    expect(screen.getByText("Allow punching from any location")).toBeTruthy();
  });

  it("asks first, then allows any location through the server and says who allowed it", async () => {
    post.mockResolvedValue({ data: { message: "Punching is now allowed from any location for these days.", data: { ...base, enforce_location: false, location_unlocked_by_name: "Hema" } } });
    render(<WfhLocationPolicy request={base} />);
    fireEvent.click(toggle());
    await waitFor(() => expect(post).toHaveBeenCalledWith(API.workFromHome.locationPolicy("r1"), { allow_any_location: true }));
    expect(await screen.findByText(/allowed from any location on these days \(allowed by Hema\)/)).toBeTruthy();
    expect(showToast).toHaveBeenCalledWith("Punching is now allowed from any location for these days.", "success");
  });

  it("does nothing when the approver declines the confirmation", async () => {
    isConfirmed = false;
    render(<WfhLocationPolicy request={base} />);
    fireEvent.click(toggle());
    await Promise.resolve();
    expect(post).not.toHaveBeenCalled();
  });

  it("can stop it again without a confirmation", async () => {
    post.mockResolvedValue({ data: { message: "Punches must be near the declared location again.", data: { ...base, enforce_location: true } } });
    render(<WfhLocationPolicy request={{ ...base, enforce_location: false, location_unlocked_by_name: "Hema" }} />);
    fireEvent.click(toggle());
    await waitFor(() => expect(post).toHaveBeenCalledWith(API.workFromHome.locationPolicy("r1"), { allow_any_location: false }));
    expect(await screen.findByText("Punches must be near Home, Kondapur.")).toBeTruthy();
  });

  it("shows a server refusal and keeps the old state", async () => {
    post.mockRejectedValue({ response: { data: { message: "You are not authorised to change this request." } } });
    render(<WfhLocationPolicy request={base} />);
    fireEvent.click(toggle());
    await waitFor(() => expect(showToast).toHaveBeenCalledWith("You are not authorised to change this request.", "error"));
    expect(screen.getByText("Punches must be near Home, Kondapur.")).toBeTruthy();
  });

  it("shows the state but no switch to someone who may not change it, and nothing for a closed request", () => {
    const { rerender } = render(<WfhLocationPolicy request={{ ...base, can_set_location_policy: false }} />);
    expect(screen.queryByText("Allow punching from any location")).toBeNull();
    expect(screen.getByText("Punches must be near Home, Kondapur.")).toBeTruthy();
    rerender(<WfhLocationPolicy request={{ ...base, status: "rejected" }} />);
    expect(screen.queryByText("Location check")).toBeNull();
  });
});
