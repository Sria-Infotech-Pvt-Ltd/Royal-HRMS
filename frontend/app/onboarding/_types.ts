export interface ProfileForm {
  date_of_birth: string; gender: string; marital_status: string;
  father_name: string; blood_group: string;
  current_address: string; current_address_line2: string;
  current_village: string; current_district: string; current_state: string; current_pin_code: string;
  permanent_address: string; permanent_address_line2: string;
  permanent_village: string; permanent_district: string; permanent_state: string; permanent_pin_code: string;
  // Holds "true"/"false" (not a real boolean) — every ProfileForm value is a
  // string, same convention custom checkbox fields already use (see
  // OnboardingDynamicField's checkbox branch).
  permanent_same_as_current: string;
  highest_qualification: string; institution: string;
  year_of_passing: string; specialization: string;
  total_experience_years: string; previous_employer: string;
  previous_designation: string; leaving_reason: string;
  account_number: string; ifsc_code: string; bank_name: string;
  bank_branch_name: string; account_holder_name: string; account_type: string;
  emergency_name: string; emergency_relationship: string;
  emergency_phone: string; emergency_email: string;
  pan_number: string;
}
