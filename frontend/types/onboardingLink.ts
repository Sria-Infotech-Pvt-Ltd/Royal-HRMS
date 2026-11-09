export interface OnboardingLinkUser {
  id: string;
  email: string;
  full_name: string;
  designation?: string;
  branch?: string;
  permissions?: string[];
  onboarding_status?: string;
  requires_self_service_onboarding?: boolean;
  assessment_status?: string;
  can_manage_team?: boolean;
  can_manage_branch?: boolean;
}

export interface OnboardingLinkResponse {
  data: { user: OnboardingLinkUser };
}

export interface HrContact {
  name: string;
  email: string;
}
