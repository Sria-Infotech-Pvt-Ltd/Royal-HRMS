// Server-side session reader — reads user info the client stored after
// a direct backend login. No JWT verification needed here; the backend
// already authenticated the user and returned a token.
import { cookies } from "next/headers";
import { USER_COOKIE } from "./auth";

export interface SessionPayload {
  userId:            string;
  email:             string;
  name:              string;
  designation:       string;
  permissions:       string[];
  /** Present in the login cookie; read by the home-screen choice (lib/dashboardHome.ts). */
  is_superuser?:     boolean;
  can_manage_team?:  boolean;
}

export async function getSession(): Promise<SessionPayload | null> {
  const cookieStore = await cookies();
  const raw = cookieStore.get(USER_COOKIE)?.value;
  if (!raw) return null;
  try {
    return JSON.parse(decodeURIComponent(raw)) as SessionPayload;
  } catch {
    return null;
  }
}
