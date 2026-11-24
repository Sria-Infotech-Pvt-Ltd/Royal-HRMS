"use client";

import { useRouter } from "next/navigation";
import { useT } from "@/hooks/useI18n";
import EmployeeCodeSeriesCard from "./_components/EmployeeCodeSeriesCard";

// Employee IDs are 8-digit, purely numeric, one disjoint range per worker type (see EmployeeCodeSeriesCard). There is no global
// prefix/padding format to configure any more, so this page just hosts the ranges.
export default function EmployeeCodeSettingsPage() {
  const router = useRouter();
  const t = useT();

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">{t("Employee ID Ranges")}</div>
          <div className="page-sub">{t("Each worker type has its own 8-digit numeric ID range")}</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> {t("Back")}
          </button>
        </div>
      </div>

      <EmployeeCodeSeriesCard />
    </>
  );
}
