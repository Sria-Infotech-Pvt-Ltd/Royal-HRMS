"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { CompanyListResponse, PlatformAdminInfo } from "@/types/platformAdmin";
import CompaniesTable from "./_components/CompaniesTable";
import AddCompanyModal from "./_components/AddCompanyModal";
import SmtpSettingsModal from "./_components/SmtpSettingsModal";

export default function PlatformAdminPage() {
  const router = useRouter();
  const { data: me } = useFetch<PlatformAdminInfo>(API.platformAdmin.me, platformAdminApi);
  const { data: companyList, loading, error, refetch } =
    useFetch<CompanyListResponse>(API.platformAdmin.companies.list, platformAdminApi);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showSmtpModal, setShowSmtpModal] = useState(false);

  // Auto-refresh while any company is still provisioning in the background,
  // so "Pending" flips to "Active" (and the credentials button appears)
  // without the platform admin needing to manually reload the page.
  const hasPending = (companyList?.results ?? []).some(c => c.provisioning_status === "pending");
  useEffect(() => {
    if (!hasPending) return;
    const interval = setInterval(refetch, 10000);
    return () => clearInterval(interval);
  }, [hasPending, refetch]);

  async function handleLogout() {
    try {
      await platformAdminApi.post(API.platformAdmin.logout);
    } finally {
      router.push("/platform-admin/login");
    }
  }

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>Companies</h1>
          {me && <p className="text-muted" style={{ fontSize: 13 }}>Signed in as {me.full_name || me.email}</p>}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-ghost" onClick={() => setShowSmtpModal(true)} suppressHydrationWarning>
            <i className="ti ti-mail" /> Email settings
          </button>
          <button className="btn btn-filled" onClick={() => setShowAddModal(true)} suppressHydrationWarning>
            <i className="ti ti-plus" /> Add company
          </button>
          <button className="btn btn-ghost" onClick={handleLogout} suppressHydrationWarning>
            <i className="ti ti-logout" /> Sign out
          </button>
        </div>
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
        <AddCompanyModal
          onClose={() => setShowAddModal(false)}
          onCreated={refetch}
        />
      )}

      {showSmtpModal && (
        <SmtpSettingsModal onClose={() => setShowSmtpModal(false)} />
      )}
    </div>
  );
}
