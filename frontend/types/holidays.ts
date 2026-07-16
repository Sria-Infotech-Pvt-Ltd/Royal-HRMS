export type HolidayType = "national" | "regional" | "company";

export interface Holiday {
  id:                   string;
  name:                 string;
  date:                 string;
  day:                  string;
  holiday_type:         HolidayType;
  holiday_type_display: string;
  is_optional:          boolean;
  mandatory_optional:   string;
  description:          string;
  branch:               number | null;
  branch_name:          string;
  is_active:            boolean;
  created_at:           string;
}

export interface HolidayListData {
  total:    number;
  holidays: Holiday[];
}

export interface HolidayFormPayload {
  name:         string;
  date:         string;
  holiday_type: HolidayType;
  is_optional:  boolean;
  description:  string;
  branch:       number | null;
  is_active:    boolean;
}
