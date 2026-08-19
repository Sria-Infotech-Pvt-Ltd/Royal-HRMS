"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { CompanyListResponse } from "@/types/platformAdmin";
import CompaniesTable from "../_components/CompaniesTable";
import AddCompanyModal from "../_components/AddCompanyModal";

export default function CompaniesPage() {
  const { data: companyList, loading, error, refetch } =
    useFetch<CompanyListResponse>(API.platformAdmin.companies.list, platformAdminApi);
  const [showAddModal, setShowAddModal] = useState(false);

  const hasPending = (companyList?.results ?? []).some(c => c.provisioning_status === "pending");
  useEffect(() => {
    if (!hasPending) return;
    const interval = setInterval(refetch, 10000);
    return () => clearInterval(interval);
  }, [hasPending, refetch]);

  return (
    <div style={{ padding: "32px 24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Companies</h1>
        <button className="btn btn-filled" onClick={() => setShowAddModal(true)} suppressHydrationWarning>
          <i className="ti ti-plus" /> Add company
        </button>
      </div>

      <div className="card">
        <div className="card-body" style={{ padding: 0 }}>
          {loading ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 spin" /> Loading companies…
            </div>
          ) : error ? (
            <div className="alert alert-warn" style={{ margin: 16 }}>
              <i className="ti ti-alert-triangle" />
              <div>{error}</div>
            </div>
          ) : (
            <CompaniesTable companies={companyList?.results ?? []} onChanged={refetch} />
          )}
        </div>
      </div>

      {showAddModal && (
        <AddCompanyModal onClose={() => setShowAddModal(false)} onCreated={refetch} />
      )}
    </div>
  );
}
