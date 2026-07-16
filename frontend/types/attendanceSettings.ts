export interface WorkingHoursSection {
  shift_start: string;           // "HH:MM" in form — converted to "HH:MM:SS" on save
  shift_end: string;
  grace_period_minutes: number;
  break_duration_minutes: number;
}

export interface WeeklyOffSection {
  monday: boolean;
  tuesday: boolean;
  wednesday: boolean;
  thursday: boolean;
  friday: boolean;
  saturday: boolean;
  sunday: boolean;
}

export interface PunchRulesSection {
  min_hours_full_day: string;       // "8.00"
  min_hours_half_day: string;       // "4.00"
  early_exit_grace_minutes: number;
}

export interface OvertimeRulesSection {
  ot_threshold_hours: string;       // "9.00"
  ot_multiplier_regular: string;    // "1.50"
  ot_multiplier_holiday: string;    // "2.00"
}

export interface LateMarkRulesSection {
  late_marks_per_lop: number;       // 0 = tracking only (no LOP deduction)
  lop_deduction_unit: string;       // "full_day" | "half_day"
}

export interface AbsenceAlertSection {
  is_enabled: boolean;
  alert_after_days: number;
  notify_whom: string;              // "manager_and_hr" | "hr_only" | "manager_only"
}

export interface AttendanceSettingsForm {
  working_hours: WorkingHoursSection;
  weekly_off: WeeklyOffSection;
  punch_rules: PunchRulesSection;
  overtime_rules: OvertimeRulesSection;
  late_mark_rules: LateMarkRulesSection;
  absence_alert: AbsenceAlertSection;
}

export type AttendanceSettingsApiResponse = {
  id?: string;
  working_hours?: Partial<WorkingHoursSection>;
  weekly_off?: Partial<WeeklyOffSection>;
  punch_rules?: Partial<PunchRulesSection>;
  overtime_rules?: Partial<OvertimeRulesSection>;
  late_mark_rules?: Partial<LateMarkRulesSection>;
  absence_alert?: Partial<AbsenceAlertSection>;
};

export type FieldErrors = Record<string, Record<string, string[]>>;
