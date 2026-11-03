"use client";

import { useRouter } from "next/navigation";
import EmployeeCodeSeriesCard from "./_components/EmployeeCodeSeriesCard";

// Employee IDs are now 8-digit, purely numeric, one disjoint range per
// worker type (see EmployeeCodeSeriesCard) — there is no global
// prefix/padding format to configure any more, so this page just hosts
// that one card.
export default function EmployeeCodeSettingsPage() {
  const router = useRouter();

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Employee ID Ranges</div>
          <div className="page-sub">Each worker type has its own 8-digit numeric ID range</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
        </div>
      </div>

      <EmployeeCodeSeriesCard />
    </>
  );
}
