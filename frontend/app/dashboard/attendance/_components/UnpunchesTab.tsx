"use client";

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useDepartmentOptions } from "@/hooks/useDepartmentOptions";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import BranchFilterSelect from "@/components/BranchFilterSelect";
import type { PaginatedUnpunches } from "@/types/attendance";
import DateInput from "@/components/shared/DateInput";
import { MONO, Notice, Pager, Pill, SectionCard, TableStates, PersonCell } from "./SectionCard";
import { PALETTE } from "./attendancePalette";
import { localISODate } from "./monthView";

interface BranchOption { id: number; branch_name: string }

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export default function UnpunchesTab() {
  const t = useT();
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);

  const [branchInput, setBranchInput] = useState("");
  const [department, setDepartment]   = useState("");
  const [date, setDate]               = useState(() => localISODate());
  const [page, setPage]               = useState(1);

  const branch = unrestricted ? branchInput : effectiveBranch;

  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(
    unrestricted ? `${API.branches.list}?page_size=100` : null
  );
  const branches    = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);
  const departments = useDepartmentOptions(unrestricted, effectiveBranch);

  const listUrl = user
    ? `${API.attendance.unPunches}${toQuery({ date, branch, department, page, page_size: 20 })}`
    : null;
  const { data, loading, error } = useFetch<PaginatedUnpunches>(listUrl);
  const rows = data?.results ?? [];

  const filters = (
    <>
      <DateInput className="field-input" style={{ width: 160 }} value={date} onChange={isoDate => { setDate(isoDate); setPage(1); }} />
      <BranchFilterSelect branches={branches} value={branchInput} onChange={value => { setBranchInput(value); setPage(1); }} locked={!unrestricted} lockedBranchName={effectiveBranch} />
      <select className="field-input field-select" style={{ width: 180 }} value={department} onChange={e => { setDepartment(e.target.value); setPage(1); }}>
        <option value="">{t("All Org Units")}</option>
        {departments.map(d => <option key={d} value={d}>{d}</option>)}
      </select>
    </>
  );

  return (
    <SectionCard icon="ti-clock-off" colour={PALETTE.late} title={t("Un-punches")} count={data?.count ?? null} filters={filters} subtitle={t("Employees who clocked in but never clocked out, for the selected date.")}>
      <Notice tone="warn" icon="ti-alert-triangle">{t("Shown once the shift end and grace period have passed without a clock-out.")}</Notice>
      {error && <Notice tone="error" icon="ti-alert-circle">{error}</Notice>}
      <div className="table-wrap" style={{ marginTop: 14 }}>
        <table>
          <thead>
            <tr><th>{t("Employee")}</th><th>{t("Company Code")}</th><th>{t("Date")}</th><th>{t("Clock In")}</th><th>{t("Expected Out")}</th><th>{t("Correction Status")}</th></tr>
          </thead>
          <tbody>
            <TableStates columns={6} loading={loading} empty={rows.length === 0} icon="ti-circle-check" title={t("No un-punches found for this date.")} hint={t("Everyone who clocked in also clocked out.")} />
            {rows.map(r => (
              <tr key={`${r.employee_id}-${r.date}`}>
                <td><PersonCell name={r.name} employeeId={r.employee_id} /></td>
                <td>{r.branch}</td>
                <td>{r.date}</td>
                <td style={{ ...MONO, fontWeight: 700 }}>{r.clock_in}</td>
                <td style={{ ...MONO, color: "var(--on-variant)" }}>{r.expected_out}</td>
                <td>{r.correction_pending ? <Pill colour={PALETTE.late}>{t("Correction Submitted")}</Pill> : <Pill colour={PALETTE.not_marked}>{t("No Correction Filed")}</Pill>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager data={data} page={page} onPage={setPage} />
    </SectionCard>
  );
}
