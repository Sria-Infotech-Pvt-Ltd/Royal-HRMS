"use client";

// State and rules behind the Employee Directory's "Basic pay" dialog: the effective-dated pay history, the
// editable record (start date, reason, pay scale, earnings overrides), the live monthly breakup, and the
// save. Saving the record already in force updates it in place; saving a later date closes it the day before
// and opens a new one (the server enforces both and the payroll.edit permission — this only reflects them).

import { useEffect, useMemo, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import {
  annualCtcToSave,
  buildPay,
  DEFAULT_VISIBLE_PAY_LINE_CODES,
  isMetro,
  professionalTaxState,
  type EarningOverrides,
  type OverrideKey,
} from "@/lib/payBreakup";
import { formatDateSlash } from "@/lib/formatDate";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import type {
  CtcRevisionReason,
  EmployeeSalaryConfig,
  PayrollSettings,
  SalaryStructure,
  SalaryStructureListItem,
} from "@/types/payroll";

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
const nextPayrollCycleStart = (startDay: number) => {
  const today = new Date();
  let year = today.getFullYear();
  let month = today.getMonth();
  const cycleDate = (targetYear: number, targetMonth: number) =>
    new Date(targetYear, targetMonth, Math.min(startDay, new Date(targetYear, targetMonth + 1, 0).getDate()));
  let start = cycleDate(year, month);
  if (start <= new Date(year, month, today.getDate())) {
    month += 1;
    if (month > 11) { year += 1; month = 0; }
    start = cycleDate(year, month);
  }
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}`;
};

export function useBasicPayEditor(employee: EmployeeLike, onSaved: () => void) {
  const { showToast } = useToast();
  const history = useFetch<EmployeeSalaryConfig[]>(API.payroll.employeeSalaryHistory(employee.code));
  const detail = useFetch<DetailBits>(API.employees.detail(employee.id));
  const payrollSettings = useFetch<PayrollSettings>(API.payroll.settings);
  const structures = useFetch<SalaryStructureListItem[]>(API.payroll.structures);

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
  const [salaryStructureId, setSalaryStructureId] = useState("");
  const [seeded, setSeeded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const selectedStructure = useFetch<SalaryStructure>(
    salaryStructureId ? API.payroll.structure(salaryStructureId, effectiveFrom) : null,
  );

  // Start from the record in force once it has loaded (or from sensible defaults when there is none).
  useEffect(() => {
    if (seeded || history.loading || detail.loading || structures.loading) return;
    const grade = (detail.data?.position_grade ?? "").slice(0, 2);
    if (current) {
      setEffectiveFrom(current.effective_from);
      setReason((current.reason || "initial") as CtcRevisionReason);
      setGroup(current.pay_scale_group || (SCALE_GROUPS.includes(grade) ? grade : "L2"));
      setLevel(current.pay_scale_level || "01");
      setBasicPercent(current.basic_percent || 40);
      setAnnualCtc(String(Math.round(Number(current.annual_ctc))));
      setOverrides(current.earnings_override ?? {});
      setSalaryStructureId(current.resolved_salary_structure ?? current.salary_structure ?? "");
    } else {
      setGroup(SCALE_GROUPS.includes(grade) ? grade : "L2");
      setSalaryStructureId(structures.data?.find(structure => structure.is_default)?.id ?? "");
    }
    setSeeded(true);
  }, [seeded, history.loading, detail.loading, structures.loading, structures.data, current, detail.data]);

  function changeSalaryStructure(id: string) {
    if (id === salaryStructureId) return;
    setSalaryStructureId(id);
    setOverrides({});
    if (current) {
      setEffectiveFrom(nextPayrollCycleStart(payrollSettings.data?.cycle_start_day ?? 1));
    }
  }

  const location = detail.data?.work_location || employee.location || "";
  const ctcNumber = Number(annualCtc);
  const structureComponents = selectedStructure.data?.components;
  const effectiveOverrides = useMemo(() => {
    const fresh = { ...overrides };
    for (const component of structureComponents ?? []) {
      if (!component.is_active || !component.reset_override || !current || current.effective_from >= component.effective_from) continue;
      delete fresh[component.code];
      const legacyKey = {
        basic: "basic",
        da: "da",
        "dearness allowance": "da",
        hra: "hra",
        "conveyance allowance": "conv",
        "medical allowance": "med",
        "leave travel allowance": "lta",
      }[component.name.toLowerCase()];
      if (legacyKey) delete fresh[legacyKey];
    }
    return fresh;
  }, [overrides, structureComponents, current]);
  const breakup = useMemo(
    () => buildPay(ctcNumber > 0 ? Math.round(ctcNumber / 12) : 0, {
      basicPercent,
      isMetroLocation: isMetro(location),
      professionalTaxState: professionalTaxState(location),
      overrides: effectiveOverrides,
      // Always the structure's own components: with none, nothing is invented from a fixed legacy list.
      components: structureComponents ?? [],
    }),
    [ctcNumber, basicPercent, location, effectiveOverrides, structureComponents],
  );
  // The breakup rounds each component to a whole monthly rupee, so re-summing
  // and ×12'ing it drifts from the entered amount whenever annual CTC isn't
  // evenly divisible by 12 (400000 -> 399996). With no overrides, the
  // breakup is purely a cosmetic display of how the typed CTC splits up, so
  // the literal typed value is what should actually be saved. Overrides are
  // the one case where the real total genuinely can differ from what was
  // typed (an admin explicitly changed a component's amount), so only then
  // is the resummed breakup the correct annual figure.
  const hasOverrides = Object.keys(effectiveOverrides).length > 0;
  const annualCostToCompany = annualCtcToSave(ctcNumber, breakup.monthlyCtc, hasOverrides);
  const variance = current ? annualCostToCompany - Math.round(Number(current.annual_ctc)) : 0;
  const visiblePayLineCodes = payrollSettings.data?.basic_pay_visible_lines ?? DEFAULT_VISIBLE_PAY_LINE_CODES;

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
      salary_structure: salaryStructureId || null,
      pay_scale_group: group, pay_scale_level: level, basic_percent: basicPercent, earnings_override: effectiveOverrides,
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
    rows, current,
    loading: history.loading || detail.loading || payrollSettings.loading || structures.loading || selectedStructure.loading || !seeded,
    loadError: history.error || detail.error || payrollSettings.error || structures.error || selectedStructure.error,
    detail: detail.data, location,
    structures: structures.data ?? [],
    selectedStructure: selectedStructure.data,
    hasStructure: !!structureComponents,
    form: {
      effectiveFrom, setEffectiveFrom, reason, setReason, group, setGroup, level, setLevel,
      basicPercent, changeBasicPercent, annualCtc, setAnnualCtc, salaryStructureId,
      setSalaryStructure: changeSalaryStructure,
    },
    breakup, annualCostToCompany, variance, hasOverrides, visiblePayLineCodes,
    setOverride, resetOverrides: () => setOverrides({}),
    delimitNote, delimitIsError: startsBeforeCurrent, formError, saving, save,
  };
}
