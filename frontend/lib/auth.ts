// Client-side auth helpers — run in the browser only.

export const AUTH_COOKIE = "royal_hrms_auth";
export const USER_COOKIE = "royal_hrms_user";

const COOKIE_MAX_AGE = 60 * 60 * 8; // 8 hours

export interface UserInfo {
  userId:              string;
  companyCode:         string;
  companyName:         string;
  companyLogoUrl:      string | null;
  companyBrandColor:   string;
  email:             string;
  name:              string;
  role:              string;
  branch:            string;
  permissions:       string[];
  onboarding_status: string;   // 'pending' | 'submitted' | 'complete'
  assessment_status: string;   // 'pending' | 'complete'
  can_manage_team:   boolean;
  can_manage_branch: boolean;
  is_superuser:      boolean;
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

// Branch scoping — the backend already enforces this server-side for hr_admin
// (it ignores/overrides any ?branch= param and returns only that user's branch).
// These helpers exist so the UI stays consistent with what the API actually
// returns, rather than showing an "All Branches" option that silently no-ops.
export function isUnrestrictedUser(user: UserInfo | null): boolean {
  // is_superuser alone misses real System Admin accounts — that Django flag
  // is only ever set by User.objects.create_superuser() (called once per
  // company during provisioning, for that company's first admin), while
  // system_admin-role users created afterward through the normal employee
  // flow don't get it (and so carry a branch, like any other employee).
  // Note: `manage.py createsuperuser` itself creates a platform-wide
  // PlatformAdmin now, not a tenant User — unrelated to this flag.
  // settings.edit is the permission the backend itself
  // already treats as "full org-wide bypass" everywhere else (leave, expense,
  // attendance, dashboard, accounts, recruitment) — check it here too so this
  // matches what the API actually does instead of drifting from it.
  return user?.is_superuser === true || (user?.permissions?.includes("settings.edit") ?? false);
}

export function getEffectiveBranch(user: UserInfo | null): string {
  return isUnrestrictedUser(user) ? "" : (user?.branch ?? "");
}
