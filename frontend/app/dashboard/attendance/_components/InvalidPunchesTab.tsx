"use client";

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import type { InvalidPunch, PaginatedInvalidPunches } from "@/types/attendance";
import AssignPunchModal from "./AssignPunchModal";
import DiscardPunchModal from "./DiscardPunchModal";
import ConvertPunchModal from "./ConvertPunchModal";
import { MONO, Notice, Pager, Pill, SectionCard, TableStates } from "./SectionCard";
import { PALETTE } from "./attendancePalette";

interface Props {
  onMutated?: () => void;
}

const ISSUE_COLOUR: Record<string, string> = {
  "no-match":  PALETTE.absent,
  duplicate:   PALETTE.late,
  future:      PALETTE.absent,
};

type ModalState =
  | { type: "assign";  punch: InvalidPunch }
  | { type: "discard"; punch: InvalidPunch }
  | { type: "convert"; punch: InvalidPunch }
  | null;

export default function InvalidPunchesTab({ onMutated }: Props) {
  const t = useT();
  const canEdit         = usePermission("attendance.edit");
  const [page, setPage]   = useState(1);
  const [modal, setModal] = useState<ModalState>(null);

  const { data, loading, error, refetch } =
    useFetch<PaginatedInvalidPunches>(`${API.attendance.invalidPunches}?page=${page}&page_size=20`);
  const rows = data?.results ?? [];

  function handleResolved() {
    setModal(null);
    refetch();
    onMutated?.();
  }

  return (
    <>
      <SectionCard icon="ti-alert-triangle" colour={PALETTE.absent} title={t("Invalid Punches")} count={data?.count ?? null} subtitle={t("Punches that could not be matched to an employee or contain data errors.")}>
        <Notice tone="info" icon="ti-info-circle">{t("Review and fix each record before it affects payroll.")}</Notice>
        {error && <Notice tone="error" icon="ti-alert-circle">{error}</Notice>}
        <div className="table-wrap" style={{ marginTop: 14 }}>
          <table>
            <thead>
              <tr><th>{t("Employee")}</th><th>{t("Device ID")}</th><th>{t("Raw Punch Time")}</th><th>{t("Card / Bio ID")}</th><th>{t("Issue")}</th><th>{t("Suggested Match")}</th><th>{t("Company Code")}</th><th>{t("Action")}</th></tr>
            </thead>
            <tbody>
              <TableStates columns={8} loading={loading} empty={rows.length === 0} icon="ti-circle-check" title={t("No invalid punches found.")} hint={t("Every punch has been matched to an employee.")} />
              {rows.map(p => (
                <tr key={p.id}>
                  <td>
                    <div style={{ fontWeight: 700, color: "var(--on-bg)" }}>{p.employee_name}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.employee_code} · {p.source}</div>
                  </td>
                  <td style={{ ...MONO, color: "var(--on-bg)", fontWeight: 700 }}>{p.device_id}</td>
                  <td style={MONO}>{p.raw_time}</td>
                  <td style={MONO}>{p.biometric_id}</td>
                  <td><Pill colour={ISSUE_COLOUR[p.issue_type] ?? PALETTE.not_marked}>{p.issue}</Pill></td>
                  <td style={{ color: "var(--on-variant)", fontSize: 12 }}>{p.suggested_match}</td>
                  <td>{p.branch}</td>
                  <td>
                    {canEdit && (
                      <div style={{ display: "flex", gap: 6 }}>
                        <button className="btn btn-outline btn-sm" style={{ padding: "3px 10px", fontSize: 11, color: PALETTE.present }} onClick={() => setModal({ type: "assign", punch: p })}><i className="ti ti-user-check" /> {t("Assign")}</button>
                        <button className="btn btn-outline btn-sm" style={{ padding: "3px 10px", fontSize: 11, color: PALETTE.brand }} onClick={() => setModal({ type: "convert", punch: p })}><i className="ti ti-replace" /> {t("Convert")}</button>
                        <button className="btn btn-outline btn-sm" style={{ padding: "3px 10px", fontSize: 11, color: PALETTE.absent }} onClick={() => setModal({ type: "discard", punch: p })}><i className="ti ti-trash" /> {t("Discard")}</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pager data={data} page={page} onPage={setPage} />
      </SectionCard>

      {modal?.type === "assign" && (
        <AssignPunchModal punch={modal.punch} onClose={() => setModal(null)} onAssigned={handleResolved} />
      )}
      {modal?.type === "discard" && (
        <DiscardPunchModal punch={modal.punch} onClose={() => setModal(null)} onDiscarded={handleResolved} />
      )}
      {modal?.type === "convert" && (
        <ConvertPunchModal punch={modal.punch} onClose={() => setModal(null)} onConverted={handleResolved} />
      )}
    </>
  );
}
