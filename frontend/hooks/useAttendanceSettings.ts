import { useCallback, useEffect, useRef, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import type {
  AttendanceSettingsForm,
  AttendanceSettingsApiResponse,
  FieldErrors,
} from "@/types/attendanceSettings";

const DEFAULTS: AttendanceSettingsForm = {
  working_hours: {
    shift_start: "09:00",
    shift_end: "18:00",
    grace_period_minutes: 15,
    break_duration_minutes: 30,
  },
  weekly_off: {
    monday: false, tuesday: false, wednesday: false, thursday: false,
    friday: false, saturday: true, sunday: true,
  },
  punch_rules: {
    min_hours_full_day: "8.00",
    min_hours_half_day: "4.00",
    early_exit_grace_minutes: 30,
  },
  overtime_rules: {
    ot_threshold_hours: "9.00",
    ot_multiplier_regular: "1.50",
    ot_multiplier_holiday: "2.00",
  },
  late_mark_rules: {
    late_marks_per_lop: 3,
    lop_deduction_unit: "full_day",
  },
  absence_alert: {
    is_enabled: true,
    alert_after_days: 3,
    notify_whom: "manager_and_hr",
  },
};

function toTime(v: string | undefined): string {
  return v ? v.slice(0, 5) : "";
}

function ensureSeconds(time: string): string {
  return time.length === 5 ? `${time}:00` : time;
}

function mergeWithDefaults(api: AttendanceSettingsApiResponse): AttendanceSettingsForm {
  const wh = api.working_hours   ?? {};
  const wo = api.weekly_off      ?? {};
  const pr = api.punch_rules     ?? {};
  const ot = api.overtime_rules  ?? {};
  const lm = api.late_mark_rules ?? {};
  const aa = api.absence_alert   ?? {};
  return {
    working_hours: {
      shift_start:            toTime(wh.shift_start)           || DEFAULTS.working_hours.shift_start,
      shift_end:              toTime(wh.shift_end)             || DEFAULTS.working_hours.shift_end,
      grace_period_minutes:   wh.grace_period_minutes          ?? DEFAULTS.working_hours.grace_period_minutes,
      break_duration_minutes: wh.break_duration_minutes        ?? DEFAULTS.working_hours.break_duration_minutes,
    },
    weekly_off: {
      monday:    wo.monday    ?? DEFAULTS.weekly_off.monday,
      tuesday:   wo.tuesday   ?? DEFAULTS.weekly_off.tuesday,
      wednesday: wo.wednesday ?? DEFAULTS.weekly_off.wednesday,
      thursday:  wo.thursday  ?? DEFAULTS.weekly_off.thursday,
      friday:    wo.friday    ?? DEFAULTS.weekly_off.friday,
      saturday:  wo.saturday  ?? DEFAULTS.weekly_off.saturday,
      sunday:    wo.sunday    ?? DEFAULTS.weekly_off.sunday,
    },
    punch_rules: {
      min_hours_full_day:       pr.min_hours_full_day       ?? DEFAULTS.punch_rules.min_hours_full_day,
      min_hours_half_day:       pr.min_hours_half_day       ?? DEFAULTS.punch_rules.min_hours_half_day,
      early_exit_grace_minutes: pr.early_exit_grace_minutes ?? DEFAULTS.punch_rules.early_exit_grace_minutes,
    },
    overtime_rules: {
      ot_threshold_hours:    ot.ot_threshold_hours    ?? DEFAULTS.overtime_rules.ot_threshold_hours,
      ot_multiplier_regular: ot.ot_multiplier_regular ?? DEFAULTS.overtime_rules.ot_multiplier_regular,
      ot_multiplier_holiday: ot.ot_multiplier_holiday ?? DEFAULTS.overtime_rules.ot_multiplier_holiday,
    },
    late_mark_rules: {
      late_marks_per_lop: lm.late_marks_per_lop ?? DEFAULTS.late_mark_rules.late_marks_per_lop,
      lop_deduction_unit: lm.lop_deduction_unit  ?? DEFAULTS.late_mark_rules.lop_deduction_unit,
    },
    absence_alert: {
      is_enabled:       aa.is_enabled       ?? DEFAULTS.absence_alert.is_enabled,
      alert_after_days: aa.alert_after_days ?? DEFAULTS.absence_alert.alert_after_days,
      notify_whom:      aa.notify_whom      ?? DEFAULTS.absence_alert.notify_whom,
    },
  };
}

function buildPutPayload(form: AttendanceSettingsForm) {
  return {
    working_hours: {
      ...form.working_hours,
      shift_start: ensureSeconds(form.working_hours.shift_start),
      shift_end:   ensureSeconds(form.working_hours.shift_end),
    },
    weekly_off:      form.weekly_off,
    punch_rules:     form.punch_rules,
    overtime_rules:  form.overtime_rules,
    late_mark_rules: form.late_mark_rules,
    absence_alert:   form.absence_alert,
  };
}

function buildPatchPayload(section: keyof AttendanceSettingsForm, form: AttendanceSettingsForm) {
  if (section === "working_hours") {
    return {
      working_hours: {
        ...form.working_hours,
        shift_start: ensureSeconds(form.working_hours.shift_start),
        shift_end:   ensureSeconds(form.working_hours.shift_end),
      },
    };
  }
  return { [section]: form[section] };
}

// normaliseError in clientApi returns { message, status, data }
type NormalisedError = { message?: string; status?: number; data?: unknown };

export function useAttendanceSettings() {
  const { showToast } = useToast();
  const { data, loading, error } = useFetch<AttendanceSettingsApiResponse>(API.attendance.settings);
  const [form,          setForm]          = useState<AttendanceSettingsForm>(DEFAULTS);
  const [saving,        setSaving]        = useState(false);
  const [savingSection, setSavingSection] = useState<keyof AttendanceSettingsForm | null>(null);
  const [fieldErrors,   setFieldErrors]   = useState<FieldErrors>({});
  const hasSynced   = useRef(false);
  const initialForm = useRef<AttendanceSettingsForm>(DEFAULTS);

  useEffect(() => {
    if (hasSynced.current || loading || data === null) return;
    hasSynced.current = true;
    const merged = mergeWithDefaults(data as AttendanceSettingsApiResponse);
    setForm(merged);
    initialForm.current = merged;
  }, [data, loading]);

  const save = useCallback(async () => {
    setSaving(true);
    setFieldErrors({});
    try {
      const res = await clientApi.put(API.attendance.settings, buildPutPayload(form));
      initialForm.current = { ...form };
      const msg = (res.data as { message?: string })?.message ?? "Settings saved.";
      showToast(msg, "success");
    } catch (err: unknown) {
      const e = err as NormalisedError;
      showToast(e?.message ?? "Failed to save attendance settings.", "error");
      if (e?.data && typeof e.data === "object") setFieldErrors(e.data as FieldErrors);
    } finally {
      setSaving(false);
    }
  }, [form, showToast]);

  const saveSection = useCallback(async (section: keyof AttendanceSettingsForm) => {
    setSavingSection(section);
    setFieldErrors({});
    try {
      const res = await clientApi.patch(API.attendance.settings, buildPatchPayload(section, form));
      initialForm.current = { ...form };
      const msg = (res.data as { message?: string })?.message ?? "Settings saved.";
      showToast(msg, "success");
    } catch (err: unknown) {
      const e = err as NormalisedError;
      showToast(e?.message ?? "Failed to save attendance settings.", "error");
      if (e?.data && typeof e.data === "object") setFieldErrors(e.data as FieldErrors);
    } finally {
      setSavingSection(null);
    }
  }, [form, showToast]);

  const reset = useCallback(() => {
    setForm(initialForm.current);
    setFieldErrors({});
  }, []);

  return {
    form, setForm,
    loading, error,
    saving, savingSection,
    fieldErrors,
    save, saveSection, reset,
  };
}
