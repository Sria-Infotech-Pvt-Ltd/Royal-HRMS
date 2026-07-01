export interface PunchEntry {
  type:                "IN" | "OUT";
  time:                string;
  location:            string;
  attendance_mode:     string;
  is_inside_geofence:  boolean | null;
  calculated_distance: number | null;
}

export interface TodaySession {
  is_clocked_in:   boolean;
  punches:         PunchEntry[];
  total_seconds:   number;
  session_seconds: number;
  date_display:    string;
}

export interface AttendanceStats {
  days_present:          number;
  late_arrivals:         number;
  lop_pending:           number;
  avg_hours_per_day:     number;
  attendance_percentage: number;
  working_days:          number;
}

export interface MonthlySummary {
  working_days: number;
  days_present: number;
  days_absent:  number;
  leave_days:   number;
  half_days:    number;
  ot_hours:     string;
}

export interface DayRecord {
  status:        "present" | "late" | "absent" | "half_day" | "weekly_off" | "holiday" | "on_leave";
  clockIn:       string | null;
  clockOut:      string | null;
  hours:         string | null;
  note:          string | null;
  canRegularize: boolean;
}

export interface CalendarResponse {
  calendar: { days: Record<string, DayRecord> };
  history:  HistoryRow[];
  month:    number;
  year:     number;
}

export interface HistoryRow {
  date:          string;
  day:           string;
  clockIn:       string | null;
  clockOut:      string | null;
  hours:         string | null;
  status:        string;
  canRegularize: boolean;
}

export type PunchType       = "IN" | "OUT" | "BOTH";
export type CorrectionReason = "biometric_error" | "forgot_to_punch" | "field_work" | "system_downtime" | "other";
export type AttendanceMode   = "office" | "wfh" | "field" | "client_location" | "remote_office";
