"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { usePermission } from "@/hooks/usePermission";
import { Branch } from "@/app/dashboard/interview-list/_data";
import ReferralTable from "./ReferralTable";
import ReferralRulesTab from "./ReferralRulesTab";
import ReferSomeoneModal from "./ReferSomeoneModal";
import { type ReferralRule, type ReferralListResponse, EMPTY_FORM } from "./_data";

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ReferralsPage() {
  const currentUser      = useCurrentUser();
  const isAdmin          = usePermission("recruitment.view");
  const [myBranch,       setMyBranch]       = useState("");
  const [tab,            setTab]            = useState<"mine" | "all" | "rules">("mine");
  const [showModal,      setShowModal]      = useState(false);
  const [form,           setForm]           = useState(EMPTY_FORM);
  const [saving,         setSaving]         = useState(false);
  const [formError,      setFormError]      = useState("");
  const [submitBanner,   setSubmitBanner]   = useState(false);
  const [mySearch,       setMySearch]       = useState("");
  const [allSearch,      setAllSearch]      = useState("");

  // Pre-fill the form's branch from the user's assigned branch (UI only — backend enforces scoping)
  useEffect(() => {
    const branch = currentUser?.branch ?? "";
    if (branch) {
      setMyBranch(branch);
      setForm(prev => ({ ...prev, branch }));
    }
  }, [currentUser?.branch]);

  const { data: myData,  loading: myLoading,  error: myError,  refetch: myRefetch  } =
    useFetch<ReferralListResponse>(API.referrals.list);
  const { data: allData, loading: allLoading, error: allError } =
    useFetch<ReferralListResponse>(isAdmin ? API.referrals.all : null);
  // Only admins (recruitment.view) see the branch-select dropdown and need
  // the full org-wide branch list — regular employees only see their own
  // branch name (from currentUser.branch, already a name not an ID) as a
  // read-only label, and the backend never even accepts a submitted branch
  // from a non-admin referrer (see ReferralSubmitSerializer). Gating this
  // fetch on isAdmin avoids a 403 for every other role.
  const { data: branchData } =
    useFetch<{ results: Branch[] }>(isAdmin ? `${API.branches.list}?status=active&page_size=100` : null);
  const { data: rulesData, loading: rulesLoading } =
    useFetch<{ results: ReferralRule[] }>(API.referralRules.list);

  const myReferrals  = myData?.results  ?? [];
  const allReferrals = allData?.results ?? [];
  const branches     = branchData?.results ?? [];
  const rules        = [...(rulesData?.results ?? [])].sort((a, b) => a.order - b.order).filter(r => r.is_active);

  // Prefer backend stats from the /all/ endpoint (includes org-wide totals).
  // Fall back to computing from the current user's list when not available.
  const backendStats = allData?.stats ?? myData?.stats;

  const statCards = [
    {
      label: "Total Referred",
      value: backendStats?.total_referred ?? myReferrals.length,
      icon: "ti-users", cls: "si-primary",
    },
    {
      label: "In Pipeline",
      value: backendStats?.in_pipeline ?? myReferrals.filter(c => !["rejected", "converted"].includes(c.status)).length,
      icon: "ti-clock", cls: "si-warn",
    },
    {
      label: "Selected",
      value: backendStats?.selected ?? myReferrals.filter(c => ["selected", "offer_sent"].includes(c.status)).length,
      icon: "ti-user-check", cls: "si-success",
    },
    {
      label: "Converted",
      value: backendStats?.converted ?? myReferrals.filter(c => c.status === "converted").length,
      icon: "ti-award", cls: "si-primary",
    },
  ];

  function setField(key: keyof typeof EMPTY_FORM, value: string) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: { preventDefault(): void }) {
    e.preventDefault();
    setSaving(true);
    setFormError("");
    const notes = [
      form.relationship ? `Relationship: ${form.relationship}` : "",
      form.notes,
    ].filter(Boolean).join("\n");
    try {
      await clientApi.post(API.referrals.create, {
        name:             form.name,
        email:            form.email,
        phone:            form.phone     || undefined,
        position_applied: form.position_applied,
        branch:           form.branch    ? Number(form.branch) : undefined,
        notes:            notes          || undefined,
      });
      setShowModal(false);
      setForm({ ...EMPTY_FORM, branch: myBranch });
      setSubmitBanner(true);
      setTimeout(() => setSubmitBanner(false), 4000);
      myRefetch();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })
          ?.response?.data?.message ?? "Failed to submit referral. Please try again.";
      setFormError(msg);
    } finally {
      setSaving(false);
    }
  }

  const TABS = [
    { key: "mine"  as const, label: "My Referrals",  icon: "ti-users",     show: true    },
    { key: "all"   as const, label: "All Referrals", icon: "ti-list",      show: isAdmin },
    { key: "rules" as const, label: "Referral Rules",icon: "ti-file-text", show: true    },
  ];

  return (
    <>
      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <div className="page-title">Referrals</div>
          <div className="page-sub">Refer talented people you know and earn a bonus when they join the team.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => { setFormError(""); setForm({ ...EMPTY_FORM, branch: myBranch }); setShowModal(true); }} suppressHydrationWarning>
            <i className="ti ti-user-plus" /> Refer Someone
          </button>
        </div>
      </div>

      {/* ── Submit success banner ── */}
      {submitBanner && (
        <div className="alert alert-success" style={{ marginBottom: 16 }}>
          <i className="ti ti-circle-check" />
          <div>Referral submitted successfully! It will appear in My Referrals shortly.</div>
        </div>
      )}

      {/* ── Stats ── */}
      <div className="stats-grid">
        {statCards.map(s => (
          <div key={s.label} className="stat-card">
            <div className={`stat-icon ${s.cls}`}><i className={`ti ${s.icon}`} /></div>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value">{s.value}</div>
          </div>
        ))}
      </div>

      {/* ── Tabbed card ── */}
      <div className="card" style={{ padding: 0 }}>

        {/* Tab bar */}
        <div style={{ display: "flex", borderBottom: "1px solid var(--outline-v)" }}>
          {TABS.filter(t => t.show).map(t => (
            <button key={t.key} onClick={() => setTab(t.key)} suppressHydrationWarning
              style={{
                padding: "14px 22px", background: "none", border: "none", cursor: "pointer",
                borderBottom: tab === t.key ? "2px solid var(--primary)" : "2px solid transparent",
                color: tab === t.key ? "var(--primary)" : "var(--on-variant)",
                fontWeight: tab === t.key ? 700 : 500, fontSize: 13,
                display: "flex", alignItems: "center", gap: 7, marginBottom: -1,
              }}>
              <i className={`ti ${t.icon}`} /> {t.label}
            </button>
          ))}
        </div>

        {/* ── Tab: My Referrals ── */}
        {tab === "mine" && (
          <ReferralTable
            candidates={myReferrals} loading={myLoading} error={myError}
            search={mySearch} onSearch={setMySearch}
          />
        )}

        {/* ── Tab: All Referrals (admin/HR only) ── */}
        {tab === "all" && isAdmin && (
          <ReferralTable
            candidates={allReferrals} loading={allLoading} error={allError}
            search={allSearch} onSearch={setAllSearch}
          />
        )}

        {/* ── Tab: Referral Rules ── */}
        {tab === "rules" && (
          <ReferralRulesTab rules={rules} loading={rulesLoading} />
        )}

      </div>

      {/* ── Refer Someone Modal ── */}
      {showModal && (
        <ReferSomeoneModal
          form={form}
          setField={setField}
          formError={formError}
          saving={saving}
          isAdmin={isAdmin}
          myBranch={myBranch}
          branches={branches}
          onSubmit={handleSubmit}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}
