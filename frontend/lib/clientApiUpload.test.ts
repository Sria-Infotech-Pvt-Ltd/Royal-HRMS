// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";

// The REAL clientApi request interceptor; only the HTTP adapter (the API server) and clearAuth are replaced.
vi.mock("./auth", () => ({ clearAuth: vi.fn() }));

import clientApi from "./clientApi";

let seenTimeouts: Array<number | undefined> = [];

function ok(config: InternalAxiosRequestConfig): AxiosResponse {
  return { data: { ok: true }, status: 200, statusText: "OK", headers: {}, config };
}

beforeEach(() => {
  seenTimeouts = [];
  clientApi.defaults.adapter = async config => { seenTimeouts.push(config.timeout); return ok(config); };
});
afterEach(() => vi.restoreAllMocks());

const file = () => { const form = new FormData(); form.append("file", new File(["x"], "doc.png", { type: "image/png" })); return form; };

describe("clientApi timeouts", () => {
  it("lets an ordinary request keep the 15 second timeout", async () => {
    await clientApi.get("/leave/requests/");
    await clientApi.post("/leave/requests/", { reason: "x" });
    expect(seenTimeouts).toEqual([15000, 15000]);
  });

  it("gives a file upload two minutes, because its duration depends on the person's upload speed", async () => {
    await clientApi.post("/hire-actions/abc/documents/", file());
    expect(seenTimeouts).toEqual([120000]);
  });

  it("applies to every kind of request that carries a file", async () => {
    await clientApi.put("/employees/1/photo/", file());
    await clientApi.patch("/expenses/1/", file());
    expect(seenTimeouts).toEqual([120000, 120000]);
  });

  it("respects a timeout the caller chose for itself", async () => {
    await clientApi.post("/employees/bulk-import/", file(), { timeout: 5000 });
    await clientApi.post("/employees/bulk-import/", file(), { timeout: 300000 });
    expect(seenTimeouts).toEqual([5000, 300000]);
  });

  it("does not change the default for the whole client", () => {
    expect(clientApi.defaults.timeout).toBe(15000);
  });

  it("still sends the multipart boundary the browser sets itself (no JSON content type on a file)", async () => {
    let contentType: unknown = "unset";
    clientApi.defaults.adapter = async config => { contentType = config.headers["Content-Type"]; return ok(config); };
    await clientApi.post("/hire-actions/abc/documents/", file());
    expect(contentType).not.toBe("application/json");
  });

  it("keeps the longer timeout when the upload is retried after a silent token refresh", async () => {
    let first = true;
    clientApi.defaults.adapter = async config => {
      seenTimeouts.push(config.timeout);
      if (first) { first = false; throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, { status: 401, statusText: "Unauthorized", data: {}, headers: {}, config } as AxiosResponse); }
      return ok(config);
    };
    vi.spyOn((await import("axios")).default, "post").mockResolvedValue({ status: 200, data: {} });
    await clientApi.post("/hire-actions/abc/documents/", file());
    expect(seenTimeouts).toEqual([120000, 120000]);   // the original attempt and the retry
  });
});
