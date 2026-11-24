"use client";

// Work-from-home requests: the location check on punches. By default a punch must be near the location the employee declared. An
// approver can allow punching from any location for these days (someone who moves around); face verification still applies and every
// punch's location is still recorded. The server decides who may change it (`can_set_location_policy`).

import { useState } from "react";
import ToggleSwitch from "@/components/ToggleSwitch";
import { confirmDialog } from "@/components/DialogProvider";
import { useToast } from "@/components/ToastProvider";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import { useT } from "@/hooks/useI18n";

const OPEN_STATUSES = new Set<WorkFromHomeRequest["status"]>(["pending", "l2_pending", "approved"]);

interface WfhLocationPolicyProps {
  request: WorkFromHomeRequest;
}

export default function WfhLocationPolicy({ request }: WfhLocationPolicyProps) {
  const t = useT();
  const { showToast } = useToast();
  const [isEnforced, setIsEnforced] = useState(request.enforce_location ?? true);
  const [unlockedBy, setUnlockedBy] = useState(request.location_unlocked_by_name ?? "");
  const [isSaving, setIsSaving] = useState(false);

  if (!OPEN_STATUSES.has(request.status)) return null;
  const canChange = Boolean(request.can_set_location_policy);

  async function change(allowAny: boolean) {
    if (allowAny) {
      const isConfirmed = await confirmDialog(
        t("Let {name} punch in and out from any location on these days? Face verification still applies and the location of every punch is still recorded.", { name: request.employee_name || t("this employee") }),
      );
      if (!isConfirmed) return;
    }
    setIsSaving(true);
    try {
      const { data } = await clientApi.post<{ message?: string; data: WorkFromHomeRequest }>(
        API.workFromHome.locationPolicy(request.id), { allow_any_location: allowAny },
      );
      setIsEnforced(data.data.enforce_location ?? !allowAny);
      setUnlockedBy(data.data.location_unlocked_by_name ?? "");
      showToast(data.message || t("Location check updated."), "success");
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(message || t("Could not change the location check."), "error");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="ta-drawer-section">
      <div className="ta-drawer-label">{t("Location check")}</div>
      <p style={{ fontSize: 13, color: "var(--ta-text)", lineHeight: 1.6, marginBottom: canChange ? 10 : 0 }}>
        {isEnforced
          ? t("Punches must be near {place}.", { place: request.location_label || t("the declared location") })
          : (unlockedBy
            ? t("Punching is allowed from any location on these days (allowed by {name}).", { name: unlockedBy })
            : t("Punching is allowed from any location on these days."))}
      </p>
      {canChange && (
        <>
          <ToggleSwitch checked={!isEnforced} onChange={change} disabled={isSaving} label={t("Allow punching from any location")} />
          <p style={{ fontSize: 11.5, color: "var(--ta-text-muted)", marginTop: 6 }}>
            {t("For someone who moves around during these days. Face verification still applies.")}
          </p>
        </>
      )}
    </div>
  );
}
