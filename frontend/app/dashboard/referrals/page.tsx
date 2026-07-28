"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { Branch, Candidate, CandidateStatus, fmtDate, initials } from "@/app/dashboard/interview-list/_data";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ReferralRule {
  id:        number;
  icon:      string;
  title:     string;
  body:      string;
  order:     number;
  is_active: boolean;
}

interface ReferralStats {
  total_referred: number;
  in_pipeline:    number;
  selected:       number;
  converted:      number;
}

interface ReferralListResponse {
  results:     Candidate[];
  count:       number;
  stats:       ReferralStats;
}

// ── Status display ─────────────────────────────────────────────────────────────

const STATUS_META: Record<CandidateStatus, { label: string; cls: string }> = {
  pending:             { label: "Pending",        cls: "badge-neutral" },
  screening:           { label: "Screening",      cls: "badge-info"    },
  interview_scheduled: { label: "Scheduled",      cls: "badge-info"    },
  interview_done:      { label: "Interview Done", cls: "badge-warn"    },
  selected:            { label: "Selected",       cls: "badge-success" },
  offer_sent:          { label: "Offer Sent",     cls: "badge-success" },
  rejected:            { label: "Rejected",       cls: "badge-error"   },
  converted:           { label: "Converted",      cls: "badge-neutral" },
};

const RELATIONSHIP_OPTIONS = [
  "Friend / Acquaintance",
  "Former Colleague",
  "Professional Contact",
  "Family Member",
  "Ex-Employee at Previous Company",
  "Other",
];

const BONUS_STAGES = [
  { stage: "Referral Accepted",  bonus: "—",       note: "Candidate enters the hiring pipeline" },
  { stage: "Candidate Selected", bonus: "—",       note: "No payout at the offer stage"         },
  { stage: "90-Day Milestone",   bonus: "₹10,000", note: "Full bonus in next payroll cycle"      },
];

const EMPTY_FORM = {
  name: "", email: "", phone: "", position_applied: "", branch: "", relationship: "", notes: "",
};

// ── Candidate table (reused by both "My" and "All" tabs) ──────────────────────

function ReferralTable({
  candidates, loading, error, search, onSearch,
}: {
  candidates: Candidate[];
  loading: boolean;
  error: string | null;
  search: string;
  onSearch: (v: string) => void;
}) {
  const filtered = search
    ? candidates.filter(c =>
        `${c.name} ${c.position_applied} ${c.referral_by_name}`
          .toLowerCase().includes(search.toLowerCase()))
    : candidates;

  return (
    <>
      <div className="card-header">
        <span className="card-title">
          <i className="ti ti-users" /> {filtered.length} Referral{filtered.length !== 1 ? "s" : ""}
        </span>
        <div className="search-bar">
          <i className="ti ti-search" />
          <input placeholder="Search by name, position…" value={search}
            onChange={e => onSearch(e.target.value)} suppressHydrationWarning />
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ margin: "0 20px 12px" }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}

      <div className="table-wrap">
        {loading ? (
          <div className="text-center py-10"><i className="ti ti-loader-2 spin text-3xl" /></div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-user-plus" />
            <h3>No referrals found</h3>
            <p>Try adjusting your search or submit a new referral.</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Candidate</th><th>Position</th><th>Branch</th>
                <th>Referred By</th><th>Status</th><th>Referred On</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(c => (
                <tr key={c.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <div className="user-avatar" style={{ width: 32, height: 32, fontSize: 12, flexShrink: 0 }}>
                        {initials(c.name)}
                      </div>
                      <div>
                        <strong>{c.name}</strong>
                        <div className="text-xs text-[var(--on-variant)]">{c.email}</div>
                        {c.phone && <div className="text-xs text-[var(--on-variant)]">{c.phone}</div>}
                      </div>
                    </div>
                  </td>
                  <td>{c.position_applied}</td>
                  <td>
                    {c.branch_name
                      ? <span className="badge badge-neutral" style={{ fontSize: 11 }}>{c.branch_name}</span>
                      : <span className="text-xs text-[var(--on-variant)]">—</span>}
                  </td>
                  <td>
                    {c.referral_by_name
                      ? <span style={{ fontSize: 12, color: "#7c3aed", display: "flex", alignItems: "center", gap: 4 }}>
                          <i className="ti ti-user-plus" style={{ fontSize: 11 }} />{c.referral_by_name}
                        </span>
                      : <span className="text-xs text-[var(--on-variant)]">—</span>}
                  </td>
                  <td>
                    <span className={`badge ${STATUS_META[c.status]?.cls ?? "badge-neutral"}`}>
                      {STATUS_META[c.status]?.label ?? c.status}
                    </span>
                  </td>
                  <td className="text-xs">{fmtDate(c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ReferralsPage() {
  const [isAdmin,        setIsAdmin]        = useState(false);
  const [myBranch,       setMyBranch]       = useState("");
  const [tab,            setTab]            = useState<"mine" | "all" | "rules">("mine");
  const [showModal,      setShowModal]      = useState(false);
  const [form,           setForm]           = useState(EMPTY_FORM);
  const [saving,         setSaving]         = useState(false);
  const [formError,      setFormError]      = useState("");
  const [submitBanner,   setSubmitBanner]   = useState(false);
  const [mySearch,       setMySearch]       = useState("");
  const [allSearch,      setAllSearch]      = useState("");

  // Read user cookie: detect admin/HR and capture the employee's own branch (UI only — backend enforces security)
  useEffect(() => {
    try {
      const pair = document.cookie.split(";").find(c => c.trim().startsWith("royal_hrms_user="));
      if (!pair) return;
      const raw = pair.trim().substring("royal_hrms_user=".length);
      const user = JSON.parse(decodeURIComponent(raw)) as { permissions?: string[]; branch?: string };
      setIsAdmin(user.permissions?.includes("recruitment.view") ?? false);
      const branch = user.branch ?? "";
      setMyBranch(branch);
      if (branch) setForm(prev => ({ ...prev, branch }));
    } catch { /* */ }
  }, []);

  const { data: myData,  loading: myLoading,  error: myError,  refetch: myRefetch  } =
    useFetch<ReferralListResponse>(API.referrals.list);
  const { data: allData, loading: allLoading, error: allError } =
    useFetch<ReferralListResponse>(isAdmin ? API.referrals.all : null);
  const { data: branchData } =
    useFetch<{ results: Branch[] }>(`${API.branches.list}?status=active&page_size=100`);
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
          <div style={{ padding: "28px 32px" }}>
            {rulesLoading ? (
              <div className="text-center py-10"><i className="ti ti-loader-2 spin text-3xl" /></div>
            ) : rules.length === 0 ? (
              <div className="empty-state">
                <i className="ti ti-file-text" />
                <h3>No rules configured</h3>
                <p>An admin can add referral rules from{" "}
                  <strong>Settings → Referral Rules</strong>.
                </p>
              </div>
            ) : (
              <>
                <div className="alert alert-info" style={{ marginBottom: 24 }}>
                  <i className="ti ti-info-circle" />
                  <div>These rules govern the Employee Referral Programme. Please read them carefully before submitting a referral.</div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))", gap: 20, marginBottom: 28 }}>
                  {rules.map((rule, idx) => (
                    <div key={rule.id} style={{ border: "1px solid var(--outline-v)", borderRadius: 14, padding: "20px 22px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
                        <div style={{ width: 38, height: 38, borderRadius: 10, background: "rgba(30,78,140,0.09)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                          <i className={`ti ${rule.icon}`} style={{ fontSize: 18, color: "var(--primary)" }} />
                        </div>
                        <div>
                          <span style={{ fontSize: 10, fontWeight: 700, color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                            Rule {idx + 1}
                          </span>
                          <p style={{ fontWeight: 700, fontSize: 14, color: "var(--on-bg)", margin: 0 }}>{rule.title}</p>
                        </div>
                      </div>
                      <p style={{ fontSize: 13, color: "var(--on-variant)", lineHeight: 1.65, margin: 0 }}>{rule.body}</p>
                    </div>
                  ))}
                </div>

                {/* Bonus breakdown */}
                <div style={{ border: "1px solid var(--outline-v)", borderRadius: 14, overflow: "hidden" }}>
                  <div style={{ background: "var(--primary)", padding: "14px 22px" }}>
                    <p style={{ fontWeight: 700, fontSize: 14, color: "#fff", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
                      <i className="ti ti-award" /> Referral Bonus Breakdown
                    </p>
                  </div>
                  <div style={{ padding: 20 }}>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
                      {BONUS_STAGES.map(item => (
                        <div key={item.stage} style={{ textAlign: "center", padding: 16, borderRadius: 10, background: "var(--bg)", border: "1px solid var(--outline-v)" }}>
                          <p style={{ fontSize: 11, color: "var(--on-variant)", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.05em" }}>{item.stage}</p>
                          <p style={{ fontSize: 22, fontWeight: 800, color: item.bonus === "—" ? "var(--on-variant)" : "#16a34a", margin: "0 0 6px" }}>{item.bonus}</p>
                          <p style={{ fontSize: 11, color: "var(--on-variant)", margin: 0 }}>{item.note}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

      </div>

      {/* ── Refer Someone Modal ── */}
      {showModal && (
        <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) setShowModal(false); }}>
          <div className="modal" style={{ width: "min(680px, 95vw)" }}>

            {/* Modal header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 24px", borderBottom: "1px solid var(--outline-v)" }}>
              <div>
                <p style={{ fontWeight: 700, fontSize: 16, color: "var(--on-bg)", margin: 0 }}>Refer Someone</p>
                <p style={{ fontSize: 12, color: "var(--on-variant)", margin: 0 }}>Share a great candidate and earn a referral bonus</p>
              </div>
              <button
                style={{ width: 32, height: 32, borderRadius: 8, border: "none", background: "var(--bg)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, color: "var(--on-variant)" }}
                onClick={() => setShowModal(false)} suppressHydrationWarning>
                <i className="ti ti-x" />
              </button>
            </div>

            {/* Modal body */}
            <div style={{ padding: "24px" }}>
              {formError && (
                <div className="alert alert-error" style={{ marginBottom: 20 }}>
                  <i className="ti ti-alert-circle" /><div>{formError}</div>
                </div>
              )}

              <form onSubmit={handleSubmit}>
                <p style={{ fontWeight: 700, fontSize: 11, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 16 }}>
                  Candidate Information
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px 20px", marginBottom: 16 }}>
                  <div className="field-group">
                    <label className="field-label">Full Name <span style={{ color: "var(--error)" }}>*</span></label>
                    <input className="field-input" placeholder="e.g. Rahul Sharma"
                      value={form.name} onChange={e => setField("name", e.target.value)}
                      required suppressHydrationWarning />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Email Address <span style={{ color: "var(--error)" }}>*</span></label>
                    <input type="email" className="field-input" placeholder="candidate@email.com"
                      value={form.email} onChange={e => setField("email", e.target.value)}
                      required suppressHydrationWarning />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Phone Number</label>
                    <input className="field-input" placeholder="+91 9876543210"
                      value={form.phone} onChange={e => setField("phone", e.target.value)}
                      suppressHydrationWarning />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Position Applied For <span style={{ color: "var(--error)" }}>*</span></label>
                    <input className="field-input" placeholder="e.g. Senior Developer"
                      value={form.position_applied} onChange={e => setField("position_applied", e.target.value)}
                      required suppressHydrationWarning />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Branch</label>
                    <div className="field-input" style={{ background: "var(--bg)", color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 8, cursor: "default" }}>
                      <i className="ti ti-building" style={{ fontSize: 14, flexShrink: 0 }} />
                      {branches.find(b => String(b.id) === String(myBranch))?.branch_name ?? (myBranch ? "Your Branch" : "Not assigned")}
                    </div>
                  </div>
                  <div className="field-group">
                    <label className="field-label">Your Relationship <span style={{ color: "var(--error)" }}>*</span></label>
                    <select className="field-input field-select"
                      value={form.relationship} onChange={e => setField("relationship", e.target.value)}
                      required suppressHydrationWarning>
                      <option value="">Select relationship</option>
                      {RELATIONSHIP_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </div>
                </div>
                <div className="field-group" style={{ marginBottom: 20 }}>
                  <label className="field-label">Why would they be a great fit?</label>
                  <textarea className="field-input" rows={3}
                    placeholder="Share their experience, skills, and why you're recommending them…"
                    value={form.notes} onChange={e => setField("notes", e.target.value)}
                    suppressHydrationWarning style={{ resize: "vertical" }} />
                </div>
                <div className="alert alert-info" style={{ marginBottom: 20 }}>
                  <i className="ti ti-info-circle" />
                  <div>By submitting this referral you confirm the candidate has consented to share their information and has not applied in the last 12 months.</div>
                </div>
                <div style={{ display: "flex", gap: 12 }}>
                  <button type="submit" className="btn btn-filled" disabled={saving} suppressHydrationWarning>
                    {saving ? <><i className="ti ti-loader-2 spin" /> Submitting…</> : <><i className="ti ti-send" /> Submit Referral</>}
                  </button>
                  <button type="button" className="btn btn-ghost" onClick={() => setShowModal(false)} suppressHydrationWarning>
                    Cancel
                  </button>
                </div>
              </form>
            </div>

          </div>
        </div>
      )}
    </>
  );
}
