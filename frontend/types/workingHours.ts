export interface WorkingHoursPolicy {
  id: string;
  name: string;
  policy_code: string;
  description: string;
  start_time: string;              // "HH:MM:SS" from backend
  end_time: string;                // "HH:MM:SS" from backend
  break_duration: number;          // minutes
  grace_period: number;            // minutes
  standard_working_hours: number;  // hours (float)
  minimum_working_hours: string;   // decimal string e.g. "8.00"
  maximum_working_hours: string;   // decimal string e.g. "10.00"
  is_default: boolean;
  is_active: boolean;
  created_by: string;
  created_by_name: string;
  updated_by: string;
  updated_by_name: string;
  created_at: string;
  updated_at: string;
}

// Form stores times as "HH:MM" (HTML time input format); conversion to "HH:MM:SS"
// happens in the save handler before sending to the backend.
export interface WorkingHoursPolicyForm {
  name: string;
  policy_code: string;
  description: string;
  start_time: string;
  end_time: string;
  break_duration: number;
  grace_period: number;
  standard_working_hours: number;
  minimum_working_hours: string;
  maximum_working_hours: string;
  is_default: boolean;
  is_active: boolean;
}
