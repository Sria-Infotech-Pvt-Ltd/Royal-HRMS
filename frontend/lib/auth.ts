// Client-side auth helpers — run in the browser only.

export const AUTH_COOKIE = "royal_hrms_auth";
export const USER_COOKIE = "royal_hrms_user";

const COOKIE_MAX_AGE = 60 * 60 * 8; // 8 hours

export interface UserInfo {
  userId:            string;
  email:             string;
  name:              string;
  role:              string;
  branch:            string;
  permissions:       string[];
  onboarding_status: string;   // 'pending' | 'submitted' | 'complete'
  assessment_status: string;   // 'pending' | 'complete'
}

export function saveAuth(user: UserInfo) {
  // Signal cookie — lets middleware know the user is authenticated
  document.cookie = `${AUTH_COOKIE}=1; path=/; max-age=${COOKIE_MAX_AGE}; samesite=lax`;
  // User info cookie — lets server components and middleware read name/role/permissions
  document.cookie = `${USER_COOKIE}=${encodeURIComponent(JSON.stringify(user))}; path=/; max-age=${COOKIE_MAX_AGE}; samesite=lax`;
}

export function clearAuth() {
  document.cookie = `${AUTH_COOKIE}=; path=/; max-age=0`;
  document.cookie = `${USER_COOKIE}=; path=/; max-age=0`;
}

export function setOnboardingStatus(newStatus: string) {
  const user = getStoredUser();
  if (user) saveAuth({ ...user, onboarding_status: newStatus });
}

export function setAssessmentStatus(newStatus: string) {
  const user = getStoredUser();
  if (user) saveAuth({ ...user, assessment_status: newStatus });
}

export function getStoredUser(): UserInfo | null {
  if (typeof window === "undefined") return null;
  try {
    const match = document.cookie
      .split("; ")
      .find((row) => row.startsWith(`${USER_COOKIE}=`));
    if (!match) return null;
    const raw = decodeURIComponent(match.split("=").slice(1).join("="));
    return JSON.parse(raw) as UserInfo;
  } catch {
    return null;
  }
}
