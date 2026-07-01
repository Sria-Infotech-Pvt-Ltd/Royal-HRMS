export interface PunchEntry {
  type:                 "IN" | "OUT";
  time:                 string;
  location:             string;
  attendance_mode:      string;
  is_inside_geofence:   boolean;
  calculated_distance:  number;
}

export interface TodayData {
  is_clocked_in:  boolean;
  punches:        PunchEntry[];
  total_seconds:  number;
  session_seconds: number;
  date_display:   string;
}

export interface AttendanceStats {
  days_present:          number;
  late_arrivals:         number;
  lop_pending:           number;
  avg_hours_per_day:     number;
  attendance_percentage: number;
  working_days:          number;
}

export interface AttendanceSummary {
  working_days: number;
  days_present: number;
  days_absent:  number;
  leave_days:   number;
  half_days:    number;
  ot_hours:     string;
}

export interface CalendarDayApi {
  status:        string;
  clockIn:       string | null;
  clockOut:      string | null;
  hours:         string | null;
  note:          string | null;
  canRegularize: boolean;
}

export interface CalendarApiResponse {
  calendar: { days: Record<string, CalendarDayApi> };
  history:  HistoryEntry[];
  month:    number;
  year:     number;
}

export interface HistoryEntry {
  date:          string;
  day:           string;
  clockIn:       string | null;
  clockOut:      string | null;
  hours:         string | null;
  status:        string;
  canRegularize: boolean;
}

export interface PunchRequest {
  punch_type:      "IN" | "OUT";
  source?:         string;
  attendance_mode?: string;
  latitude?:       number;
  longitude?:      number;
  accuracy?:       number;
  device_time?:    string;
}

export type CorrectionPunchType = "IN" | "OUT" | "BOTH";

export type CorrectionReason =
  | "biometric_error"
  | "forgot_to_punch"
  | "field_work"
  | "system_downtime"
  | "other";

export interface CorrectionRequest {
  date:               string;
  punch_type:         CorrectionPunchType;
  correct_in_time?:   string;
  correct_out_time?:  string;
  reason:             CorrectionReason;
  notes?:             string;
}
