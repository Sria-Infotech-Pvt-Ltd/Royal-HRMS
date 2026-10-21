"use client";

// State and rules behind the Employee Directory's "Basic pay" dialog: the effective-dated pay history, the
// editable record (start date, reason, pay scale, earnings overrides), the live monthly breakup, and the
// save. Saving the record already in force updates it in place; saving a later date closes it the day before
// and opens a new one (the server enforces both and the payroll.edit permission — this only reflects them).

import { useEffect, useMemo, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { buildPay, isMetro, professionalTaxState, type EarningOverrides, type OverrideKey } from "@/lib/payBreakup";
import { formatDateSlash } from "@/lib/formatDate";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import type { CtcRevisionReason, EmployeeSalaryConfig } from "@/types/payroll";

export const PAY_REASONS: { value: CtcRevisionReason; label: string }[] = [
  { value: "initial", label: "Initial basic pay" },
  { value: "increment", label: "Annual revision" },
  { value: "promotion", label: "Promotion linked" },
  { value: "market_correction", label: "Market correction" },
  { value: "correction", label: "Correction" },
];

interface EmployeeLike { id: string; code: string; location?: string }

interface DetailBits {
  position_grade?: string | null;
  work_location?: string;
  org_unit_name?: string | null;
  profile?: { account_number?: string };
}

const todayIso = () => new Date().toISOString().slice(0, 10);
const dayBefore = (iso: string) => {
  const date = new Date(`${iso}T00:00:00`);
  date.setDate(date.getDate() - 1);
  return date.toISOString().slice(0, 10);
};
const SCALE_GROUPS = ["L1", "L2", "L3", "L4", "L5"];

export function useBasicPayEditor(employee: EmployeeLike, onSaved: () => void) {
  const { showToast } = useToast();
  const history = useFetch<EmployeeSalaryConfig[]>(API.payroll.employeeSalaryHistory(employee.code));
  const detail = useFetch<DetailBits>(API.employees.detail(employee.id));

  const rows = useMemo(
    () => (history.data ?? []).slice().sort((a, b) => b.effective_from.localeCompare(a.effective_from)),
    [history.data],
  );
  const current = rows.find(row => row.is_active) ?? null;

  const [effectiveFrom, setEffectiveFrom] = useState(todayIso());
  const [reason, setReason] = useState<CtcRevisionReason>("initial");
  const [group, setGroup] = useState("L2");
  const [level, setLevel] = useState("01");
  const [basicPercent, setBasicPercent] = useState(40);
  const [annualCtc, setAnnualCtc] = useState("");
  const [overrides, setOverrides] = useState<EarningOverrides>({});
  const [seeded, setSeeded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  // Start from the record in force once it has loaded (or from sensible defaults when there is none).
  useEffect(() => {
    if (seeded || history.loading || detail.loading) return;
    const grade = (detail.data?.position_grade ?? "").slice(0, 2);
    if (current) {
      setEffectiveFrom(current.effective_from);
      setReason((current.reason || "initial") as CtcRevisionReason);
      setGroup(current.pay_scale_group || (SCALE_GROUPS.includes(grade) ? grade : "L2"));
      setLevel(current.pay_scale_level || "01");
      setBasicPercent(current.basic_percent || 40);
      setAnnualCtc(String(Math.round(Number(current.annual_ctc))));
      setOverrides(current.earnings_override ?? {});
    } else {
      setGroup(SCALE_GROUPS.includes(grade) ? grade : "L2");
    }
    setSeeded(true);
  }, [seeded, history.loading, detail.loading, current, detail.data]);

  const location = detail.data?.work_location || employee.location || "";
  const ctcNumber = Number(annualCtc);
  const breakup = useMemo(
    () => buildPay(ctcNumber > 0 ? Math.round(ctcNumber / 12) : 0, {
      basicPercent, isMetroLocation: isMetro(location), professionalTaxState: professionalTaxState(location), overrides,
    }),
    [ctcNumber, basicPercent, location, overrides],
  );
  // The breakup rounds each component to a whole monthly rupee, so re-summing
  // and ×12'ing it drifts from the entered amount whenever annual CTC isn't
  // evenly divisible by 12 (400000 -> 399996). With no overrides, the
  // breakup is purely a cosmetic display of how the typed CTC splits up, so
  // the literal typed value is what should actually be saved. Overrides are
  // the one case where the real total genuinely can differ from what was
  // typed (an admin explicitly changed a component's amount), so only then
  // is the resummed breakup the correct annual figure.
  const hasOverrides = Object.keys(overrides).length > 0;
  const breakupAnnual = breakup.monthlyCtc * 12;
  const annualCostToCompany = hasOverrides ? breakupAnnual : Math.round(ctcNumber);
  const variance = current ? annualCostToCompany - Math.round(Number(current.annual_ctc)) : 0;

  const startsBeforeCurrent = !!current && !!effectiveFrom && effectiveFrom < current.effective_from;
  let delimitNote = "";
  if (current && effectiveFrom) {
    if (effectiveFrom === current.effective_from) delimitNote = `Updating the record in force from ${formatDateSlash(current.effective_from)}.`;
    else if (startsBeforeCurrent) delimitNote = `Must be on or after ${formatDateSlash(current.effective_from)}.`;
    else delimitNote = `Current record will be delimited to ${formatDateSlash(dayBefore(effectiveFrom))}; the new record runs ${formatDateSlash(effectiveFrom)} → 31/12/9999.`;
  }

  function setOverride(key: OverrideKey, value: string) {
    setOverrides(previous => ({ ...previous, [key]: Math.max(0, Math.round(Number(value) || 0)) }));
  }
  function changeBasicPercent(value: number) {
    setBasicPercent(value);
    setOverrides(previous => { const { basic: _discarded, ...rest } = previous; return rest; });
  }

  async function save() {
    if (!(ctcNumber > 0)) { setFormError("Enter an annual CTC greater than zero."); return; }
    if (!effectiveFrom) { setFormError("Start date is required."); return; }
    if (startsBeforeCurrent) { setFormError(delimitNote); return; }
    setSaving(true);
    setFormError("");
    const body = {
      annual_ctc: Math.round(annualCostToCompany), effective_from: effectiveFrom, reason,
      pay_scale_group: group, pay_scale_level: level, basic_percent: basicPercent, earnings_override: overrides,
    };
    try {
      if (current && current.effective_from === effectiveFrom) await clientApi.put(API.payroll.employeeSalaryDetail(current.id), body);
      else await clientApi.post(API.payroll.employeeSalary, { ...body, employee: employee.code });
      showToast(`Basic pay saved — ₹${Math.round(annualCostToCompany).toLocaleString("en-IN")} per annum, effective ${formatDateSlash(effectiveFrom)}.`, "success");
      history.refetch();
      onSaved();
    } catch (err: unknown) {
      setFormError((err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Could not save this pay record.");
    } finally {
      setSaving(false);
    }
  }

  return {
    rows, current, loading: history.loading || detail.loading || !seeded, loadError: history.error,
    detail: detail.data, location,
    form: { effectiveFrom, setEffectiveFrom, reason, setReason, group, setGroup, level, setLevel, basicPercent, changeBasicPercent, annualCtc, setAnnualCtc },
    breakup, annualCostToCompany, variance, hasOverrides,
    setOverride, resetOverrides: () => setOverrides({}),
    delimitNote, delimitIsError: startsBeforeCurrent, formError, saving, save,
  };
}
