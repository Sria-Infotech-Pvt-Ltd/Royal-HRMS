import { afterEach, describe, expect, it, vi } from "vitest";

// useNotifications imports React/toast modules; only the URL helper is under test.
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast: () => {} }) }));

async function urlWith(env: Record<string, string>, location?: { protocol: string; host: string }) {
  vi.resetModules();
  for (const [k, v] of Object.entries(env)) vi.stubEnv(k, v);
  if (location) vi.stubGlobal("window", { location });
  const mod = await import("./useNotifications");
  return mod.notificationsSocketUrl();
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("notificationsSocketUrl", () => {
  it("uses the page's own host in production (cookie travels with it)", async () => {
    expect(await urlWith({ NODE_ENV: "production", NEXT_PUBLIC_API_URL: "https://api.royalhrms.com" },
      { protocol: "https:", host: "royalhrms.com" })).toBe("wss://royalhrms.com/ws/notifications/");
    expect(await urlWith({ NODE_ENV: "production" }, { protocol: "http:", host: "localhost:3001" }))
      .toBe("ws://localhost:3001/ws/notifications/");
  });

  it("honours an explicit NEXT_PUBLIC_WS_URL", async () => {
    expect(await urlWith({ NODE_ENV: "production", NEXT_PUBLIC_WS_URL: "wss://ws.example.com/" },
      { protocol: "https:", host: "royalhrms.com" })).toBe("wss://ws.example.com/ws/notifications/");
  });

  it("local development keeps the API host (or none)", async () => {
    expect(await urlWith({ NODE_ENV: "development", NEXT_PUBLIC_API_URL: "http://localhost:8000" }))
      .toBe("ws://localhost:8000/ws/notifications/");
  });
});
