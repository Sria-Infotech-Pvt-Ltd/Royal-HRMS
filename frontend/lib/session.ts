// Server-side session reader — reads user info the client stored after
// a direct backend login. No JWT verification needed here; the backend
// already authenticated the user and returned a token.
import { cookies } from "next/headers";
import { USER_COOKIE } from "./auth";
import { modulesFromPayload } from "./modules";

export interface SessionPayload {
  userId:            string;
  email:             string;
  name:              string;
  role:              string;
  permissions:       string[];
  companyName?:      string;
  /** Company modules (subscription) from the access token's `modules` claim;
   *  undefined when unknown (show everything, as before). */
  modules?:          string[];
}

function accessTokenPayload(token: string | undefined): Record<string, unknown> | null {
  // Display-only read of our own httpOnly cookie (the API verifies the token).
  if (!token) return null;
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(Buffer.from(part, "base64").toString("utf8"));
  } catch {
    return null;
  }
}

export async function getSession(): Promise<SessionPayload | null> {
  const cookieStore = await cookies();
  const raw = cookieStore.get(USER_COOKIE)?.value;
  if (!raw) return null;
  try {
    const session = JSON.parse(decodeURIComponent(raw)) as SessionPayload;
    const modules = modulesFromPayload(accessTokenPayload(cookieStore.get("royal_access_token")?.value));
    return modules ? { ...session, modules } : session;
  } catch {
    return null;
  }
}
