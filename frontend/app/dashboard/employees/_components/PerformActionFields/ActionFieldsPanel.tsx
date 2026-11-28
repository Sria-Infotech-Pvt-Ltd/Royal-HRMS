"use client";

// The fields the chosen action may change, under "FIELDS THIS … MAY CHANGE" in the Perform an action modal.

import { useT } from "@/hooks/useI18n";
import type { PerformActionForm } from "@/hooks/usePerformActionForm";
import type { usePerformActionData } from "@/hooks/usePerformActionData";
import {
  PromotionFields, OrgAssignmentFields, PayChangeFields, ConfirmationFields, SeparationFields,
} from "./ActionFieldSections";

interface ActionFieldsPanelProps {
  form: PerformActionForm;
  data: ReturnType<typeof usePerformActionData>;
  currentStatusLabel: string;
}

export default function ActionFieldsPanel({ form, data, currentStatusLabel }: ActionFieldsPanelProps) {
  const t = useT();
  const { values } = form;
  switch (values.actionType) {
    case "promotion":
      return (
        <PromotionFields
          positionId={values.positionId} setPositionId={form.setPositionId} positionOptions={data.positionOptions}
          annualCtc={values.annualCtc} setAnnualCtc={form.setAnnualCtc}
        />
      );
    case "org_assignment":
      return (
        <OrgAssignmentFields
          managerId={values.managerId} setManagerId={form.setManagerId} managerOptions={data.managerOptions}
          workLocation={values.workLocation} setWorkLocation={form.setWorkLocation}
          move={{
            unitId: values.moveUnitId, setUnitId: form.setMoveUnitId, unitOptions: data.moveUnitOptions,
            positionId: values.positionId, setPositionId: form.setPositionId, positionOptions: data.movePositionOptions,
          }}
        />
      );
    case "pay_change":
      return <PayChangeFields annualCtc={values.annualCtc} setAnnualCtc={form.setAnnualCtc} />;
    case "confirmation":
      return <ConfirmationFields currentStatusLabel={currentStatusLabel} />;
    case "separation":
      return (
        <>
          <SeparationFields
            separationType={values.separationType} setSeparationType={form.setSeparationType} typeOptions={data.separationTypeOptions}
            lastWorkingDay={values.lastWorkingDay} setLastWorkingDay={form.setLastWorkingDay} resultingStatusLabel={t("Notice Period")}
          />
          <p className="hint">{t("Reason for this separation is captured in the full Separation module after this record is filed (real reason list already used there).")}</p>
        </>
      );
    default:
      return null;
  }
}
