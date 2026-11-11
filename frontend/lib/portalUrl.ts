// The Employee Portal URL: the public website address that activation emails link to (https://aira.nxsys.in/activate/<token>/).
// Mirrors the backend check (backend/apps/accounts/services_frontend_url.check_portal_url) so a bad value is caught before saving;
// the server repeats the check and is the one that decides.

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export const PORTAL_URL_HELP =
  "The public address employees open from the activation email, for example https://aira.nxsys.in (no path needed).";

/** Returns an error message for an unusable portal URL, or null when it is fine. Blank is allowed here (the server then refuses to send invitations). */
export function validatePortalUrl(raw: string, isProduction: boolean = process.env.NODE_ENV === "production"): string | null {
  const value = raw.trim();
  if (!value) return null;
  if (/\s/.test(value)) return "The portal URL must not contain spaces.";
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return "Enter a full web address starting with https://, for example https://aira.nxsys.in.";
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    return "The portal URL must start with https://.";
  }
  if (!parsed.hostname) return "The portal URL must include the website name, for example https://aira.nxsys.in.";
  const isLocal = LOCAL_HOSTS.has(parsed.hostname);
  if (!isLocal && !parsed.hostname.includes(".")) {
    return "The portal URL must be a full website name such as aira.nxsys.in, not a single word.";
  }
  if (parsed.search || parsed.hash) return "The portal URL must not contain ? or # parts.";
  if (parsed.protocol === "http:" && !(isLocal && !isProduction)) {
    return "The portal URL must use https://. Plain http:// is only allowed for localhost during development.";
  }
  return null;
}
