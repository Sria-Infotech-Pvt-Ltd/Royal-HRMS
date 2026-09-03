"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getStoredUser } from "@/lib/auth";
import { useBirthdaysToday } from "@/hooks/useEmployeeDashboard";
import type { BirthdayEmployee } from "@/types/employeeDashboard";
import type { OrgUnit } from "@/types/orgStructure";
import BirthdayCelebrationCard from "@/components/dashboard/employee/BirthdayCelebrationCard";
import BirthdayCelebrationModal from "@/components/dashboard/employee/BirthdayCelebrationModal";
import Modal from "@/components/Modal";

// ─── Types ────────────────────────────────────────────────────────────────────

type Category      = "general" | "policy" | "event" | "celebration";
type Visibility    = "all" | "department" | "branch";
// The Branch field is now its own always-present field in the form, separate
// from Visibility — so the form only ever chooses between these two; "branch"
// targeting is derived from the Branch field instead (see handleSave).
type FormVisibility = "all" | "department";

interface Announcement {
  id:                     number;
  title:                  string;
  body:                   string;
  category:               Category;
  visibility:             Visibility;
  target_org_unit:        string | null;
  target_org_unit_name:   string;
  target_branch:          number | null;
  target_branch_name:     string;
  is_pinned:              boolean;
  send_email:             boolean;
  posted_by:              string | null;
  posted_by_name:         string;
  posted_by_role:         string;
  views_count:            number;
  reactions_count:        number;
  has_reacted:            boolean;
  can_edit:               boolean;
  created_at:             string;
  updated_at:             string;
}

interface PageMeta {
  count:           number;
  page:            number;
  page_size:       number;
  total_pages:     number;
  pinned_count:    number;
  total_reactions: number;
  total_views:     number;
  results:         Announcement[];
}

interface Branch     { id: number; branch_name: string; branch_code: string }

type FormState = {
  title:             string;
  body:              string;
  category:          Category | "";
  visibility:        FormVisibility;
  target_org_unit:   string;
  target_branch:     string;
  is_pinned:         boolean;
  send_email:        boolean;
};

type FormErrors = Partial<Record<keyof FormState, string>>;

// ─── Constants ────────────────────────────────────────────────────────────────

const CATEGORIES: { value: Category; label: string }[] = [
  { value: "general",     label: "General"     },
  { value: "policy",      label: "Policy"      },
  { value: "event",       label: "Event"       },
  { value: "celebration", label: "Celebration" },
];

const VISIBILITY_OPTIONS: { value: FormVisibility; label: string }[] = [
  { value: "all",        label: "All Employees" },
  { value: "department", label: "By Department" },
];

const FILTERS = [
  { value: "",            label: "All Posts"   },
  { value: "general",     label: "General"     },
  { value: "policy",      label: "Policy"      },
  { value: "event",       label: "Event"       },
  { value: "celebration", label: "Celebration" },
];

const EMPTY_FORM: FormState = {
  title: "", body: "", category: "", visibility: "all",
  target_org_unit: "", target_branch: "",
  is_pinned: false, send_email: true,
};

// Kept for reference — no longer used; canPost is now permission-based
// const POSTER_ROLES = new Set(["hr_admin", "system_admin", "manager"]);

// ─── Helpers ──────────────────────────────────────────────────────────────────

function initials(name: string): string {
  return name.split(" ").filter(Boolean).slice(0, 2).map(w => w[0]?.toUpperCase() ?? "").join("");
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1)  return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7)  return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function fullDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

const CAT_BADGE: Record<Category, string> = {
  general:     "badge-info",
  policy:      "badge-warn",
  event:       "badge-success",
  celebration: "badge-primary",
};

const CAT_LABEL: Record<Category, string> = {
  general:     "General",
  policy:      "Policy",
  event:       "Event",
  celebration: "Celebration",
};

const AVATAR_COLORS = [
  { bg: "rgba(30,78,140,0.15)",  color: "#1e4e8c" },
  { bg: "rgba(14,124,134,0.15)", color: "#0e7c86" },
  { bg: "rgba(27,138,107,0.15)", color: "#1b8a6b" },
  { bg: "rgba(181,101,29,0.15)", color: "#b5651d" },
];
function avatarColor(name: string) {
  return AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];
}

function viewKey(id: number) { return `ann_viewed_${id}`; }

// ─── Component ────────────────────────────────────────────────────────────────

export default function AnnouncementsPage() {

  // Read localStorage only on the client to avoid SSR/hydration mismatch.
  const [currentUser, setCurrentUser] = useState<ReturnType<typeof getStoredUser>>(null);
  useEffect(() => { setCurrentUser(getStoredUser()); }, []);

  const canPost   = (currentUser?.permissions.includes("announcements.create") ?? false) || (currentUser?.is_superuser === true);
  // "settings.edit" is this codebase's existing "bypass all branch scoping,
  // treat as global admin" flag (see Branch Admin's role migration) — reused
  // here so the Branch field is unrestricted only for genuinely org-wide roles.
  const isOrgWide = (currentUser?.permissions.includes("settings.edit")       ?? false) || (currentUser?.is_superuser === true);

  // ── Data ────────────────────────────────────────────────────────────────────
  const [meta,    setMeta]    = useState<PageMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageErr, setPageErr] = useState<string | null>(null);

  // ── Filters / pagination ────────────────────────────────────────────────────
  const [category, setCategory] = useState("");
  const [page,     setPage]     = useState(1);

  // ── Modal ───────────────────────────────────────────────────────────────────
  const [showModal,  setShowModal]  = useState(false);
  const [editTarget, setEditTarget] = useState<Announcement | null>(null);
  const [form,       setForm]       = useState<FormState>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [saveErr,    setSaveErr]    = useState<string | null>(null);
  const [saving,     setSaving]     = useState(false);

  // ── Delete confirm ──────────────────────────────────────────────────────────
  const [deleteId,  setDeleteId]  = useState<number | null>(null);
  const [deleting,  setDeleting]  = useState(false);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);

  // ── Dropdown data ───────────────────────────────────────────────────────────
  const [orgUnits,    setOrgUnits]    = useState<OrgUnit[]>([]);
  const [branches,    setBranches]    = useState<Branch[]>([]);

  // The poster's own branch id, resolved from their branch name — used to lock
  // the Branch field for anyone who isn't org-wide (see isOrgWide above).
  const myBranchId = branches.find(b => b.branch_name === currentUser?.branch)?.id ?? null;

  // ── Detail view modal ───────────────────────────────────────────────────────
  const [viewTarget, setViewTarget] = useState<Announcement | null>(null);

  // ── Birthday celebration (Celebration tab) ─────────────────────────────────
  const { data: birthdayData } = useBirthdaysToday();
  const todaysBirthdays = birthdayData?.birthdays ?? [];
  const [celebrateTarget, setCelebrateTarget] = useState<BirthdayEmployee | null>(null);

  const titleRef = useRef<HTMLInputElement>(null);

  // ─── Fetch announcements ───────────────────────────────────────────────────

  const fetchAnnouncements = useCallback(async (pg: number, cat: string) => {
    setLoading(true);
    setPageErr(null);
    try {
      const params: Record<string, string> = { page: String(pg), page_size: "10" };
      if (cat) params.category = cat;
      const res = await clientApi.get(API.announcements.list, { params });
      setMeta(res.data?.data ?? null);
    } catch (e: unknown) {
      setPageErr((e as { message?: string }).message ?? "Failed to load announcements.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnnouncements(page, category);
  }, [page, category, fetchAnnouncements]);

  // Fetch org units + branches from the backend for the modal dropdowns.
  // OrgUnit has no branch field (it's one shared, branch-agnostic tree for
  // the whole company — see accounts/models.py's own OrgUnit docstring), so
  // unlike the old Department list this is always the full company-wide set.
  useEffect(() => {
    if (!canPost) return;
    clientApi.get(`${API.orgStructure.units.list}?page_size=200`)
      .then(r => setOrgUnits(r.data?.data?.results ?? [])).catch(() => {});
    clientApi.get(`${API.branches.list}?status=active&page_size=100`)
      .then(r => setBranches(r.data?.data?.results ?? [])).catch(() => {});
  }, [canPost]);

  // Track views once per card per session (non-authors only)
  useEffect(() => {
    if (!meta?.results.length) return;
    meta.results.forEach(ann => {
      const key = viewKey(ann.id);
      if (!localStorage.getItem(key) && ann.posted_by !== currentUser?.userId) {
        clientApi.post(API.announcements.view(ann.id)).then(() => {
          localStorage.setItem(key, "1");
        }).catch(() => {});
      }
    });
  // Deliberately re-runs only when the announcement list itself changes, not
  // on every currentUser identity change — re-running per user-object
  // reference would re-fire the "mark viewed" POST for cards already marked
  // this session (view state is deduped via localStorage, not React state).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta?.results]);

  // ─── Modal helpers ─────────────────────────────────────────────────────────

  // Branch-scoped (non-org-wide) posters are always locked to their own
  // branch; org-wide posters default to "All Branches" ("") and may change it.
  function defaultBranchField(): string {
    return isOrgWide ? "" : (myBranchId != null ? String(myBranchId) : "");
  }

  function openCreate() {
    setEditTarget(null);
    setForm({ ...EMPTY_FORM, send_email: canPost, target_branch: defaultBranchField() });
    setFormErrors({});
    setSaveErr(null);
    setShowModal(true);
    setTimeout(() => titleRef.current?.focus(), 80);
  }

  function openEdit(ann: Announcement) {
    setEditTarget(ann);
    setForm({
      title:             ann.title,
      body:              ann.body,
      category:          ann.category,
      visibility:        ann.visibility === "department" ? "department" : "all",
      target_org_unit:   ann.target_org_unit ?? "",
      target_branch:     isOrgWide
        ? (ann.visibility === "branch" && ann.target_branch ? String(ann.target_branch) : "")
        : defaultBranchField(),
      is_pinned:         ann.is_pinned,
      send_email:        ann.send_email,
    });
    setFormErrors({});
    setSaveErr(null);
    setShowModal(true);
    setTimeout(() => titleRef.current?.focus(), 80);
  }

  function closeModal() {
    setShowModal(false);
    setEditTarget(null);
  }

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(prev => {
      const next = { ...prev, [key]: value };
      if (key === "visibility" && value !== "department") {
        next.target_org_unit = "";
      }
      return next;
    });
    setFormErrors(prev => ({ ...prev, [key]: undefined }));
  }

  // ─── Validation ────────────────────────────────────────────────────────────

  function validate(): boolean {
    const errs: FormErrors = {};
    if (!form.title.trim())    errs.title    = "Title is required.";
    if (!form.body.trim())     errs.body     = "Body is required.";
    if (!form.category)        errs.category = "Category is required.";
    if (form.visibility === "department" && !form.target_org_unit)
      errs.target_org_unit = "Select an org unit.";
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  }

  // ─── Save ──────────────────────────────────────────────────────────────────

  async function handleSave() {
    if (!validate()) return;
    if (!isOrgWide && myBranchId == null) {
      setSaveErr("Your branch could not be resolved. Contact your administrator.");
      return;
    }
    setSaving(true);
    setSaveErr(null);
    try {
      // Visibility is now derived, not chosen directly: "By Department" always
      // wins (department reach isn't branch-limited in this system); otherwise
      // a selected Branch narrows to that branch, and no branch means company-wide.
      let apiVisibility: Visibility;
      let targetBranch: number | null;
      let targetOrgUnit: string | null;

      if (form.visibility === "department") {
        apiVisibility = "department";
        targetOrgUnit = form.target_org_unit || null;
        targetBranch  = null;
      } else if (form.target_branch) {
        apiVisibility = "branch";
        targetBranch  = Number(form.target_branch);
        targetOrgUnit = null;
      } else {
        apiVisibility = "all";
        targetBranch  = null;
        targetOrgUnit = null;
      }

      const payload: Record<string, unknown> = {
        title:           form.title.trim(),
        body:            form.body.trim(),
        category:        form.category,
        visibility:      apiVisibility,
        is_pinned:       form.is_pinned,
        send_email:      form.send_email,
        target_org_unit: targetOrgUnit,
        target_branch:   targetBranch,
      };

      // Longer timeout than the client default — posting/updating an
      // announcement (esp. with "send email" on) can take longer than the
      // usual request.
      const requestConfig = { timeout: 30000 };
      if (editTarget) {
        await clientApi.put(API.announcements.detail(editTarget.id), payload, requestConfig);
      } else {
        await clientApi.post(API.announcements.list, payload, requestConfig);
      }

      closeModal();
      setPage(1);
      fetchAnnouncements(1, category);
    } catch (e: unknown) {
      const err = e as { message?: string; code?: string };
      const message = err.code === "ECONNABORTED"
        ? "The request timed out. The announcement may still have been saved — check the list before trying again."
        : (err.message ?? "Failed to save announcement.");
      setSaveErr(message);
    } finally {
      setSaving(false);
    }
  }

  // ─── Delete ────────────────────────────────────────────────────────────────

  async function handleDelete() {
    if (deleteId == null) return;
    setDeleting(true);
    setDeleteErr(null);
    try {
      await clientApi.delete(API.announcements.detail(deleteId));
      setDeleteId(null);
      // If we delete the last item on a page > 1, go back one page
      const remaining = (meta?.results.length ?? 1) - 1;
      const newPage   = remaining === 0 && page > 1 ? page - 1 : page;
      setPage(newPage);
      fetchAnnouncements(newPage, category);
    } catch (e: unknown) {
      setDeleteErr((e as { message?: string }).message ?? "Delete failed.");
    } finally {
      setDeleting(false);
    }
  }

  // ─── React / like ──────────────────────────────────────────────────────────

  async function toggleReact(ann: Announcement) {
    if (!meta) return;
    // Optimistic update
    const delta = ann.has_reacted ? -1 : 1;
    setMeta(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        total_reactions: prev.total_reactions + delta,
        results: prev.results.map(a =>
          a.id === ann.id
            ? { ...a, has_reacted: !a.has_reacted, reactions_count: a.reactions_count + delta }
            : a
        ),
      };
    });
    try {
      await clientApi.post(API.announcements.react(ann.id));
    } catch {
      // Rollback on error
      fetchAnnouncements(page, category);
    }
  }

  // ─── Stats from API meta ───────────────────────────────────────────────────

  const stats = [
    { label: "Total Posts",     value: meta?.count           ?? 0, icon: "ti-speakerphone", cls: "si-primary" },
    { label: "Pinned",          value: meta?.pinned_count    ?? 0, icon: "ti-pin",          cls: "si-warn"    },
    { label: "Total Reactions", value: meta?.total_reactions ?? 0, icon: "ti-heart",        cls: "si-success" },
    { label: "Total Views",     value: meta?.total_views     ?? 0, icon: "ti-eye",          cls: "si-info"    },
  ];

  const BODY_PREVIEW = 220;

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <div className="page-title">Announcements</div>
          <div className="page-sub">Company-wide news, policy updates, and celebrations</div>
        </div>
        {canPost && (
          <div className="page-actions">
            <button className="btn btn-filled" onClick={openCreate}>
              <i className="ti ti-plus" /> Post Announcement
            </button>
          </div>
        )}
      </div>

      {/* ── Stat cards ───────────────────────────────────────────────────── */}
      <div className="stats-grid">
        {stats.map(s => (
          <div className="stat-card" key={s.label}>
            <div className={`stat-icon ${s.cls}`}><i className={`ti ${s.icon}`} /></div>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value">{s.value.toLocaleString()}</div>
          </div>
        ))}
      </div>

      {/* ── Category filter tabs ─────────────────────────────────────────── */}
      <div className="ann-filter-bar">
        {FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => { setCategory(f.value); setPage(1); }}
            className={`btn ${category === f.value ? "btn-filled" : "btn-ghost"}`}
            suppressHydrationWarning
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* ── Celebration: today's birthdays ───────────────────────────────── */}
      {(category === "" || category === "celebration") && todaysBirthdays.map(emp => (
        <BirthdayCelebrationCard
          key={emp.employee_id}
          employee={emp}
          onOpen={() => setCelebrateTarget(emp)}
        />
      ))}

      {/* ── Error ────────────────────────────────────────────────────────── */}
      {pageErr && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> {pageErr}
        </div>
      )}

      {/* ── Loading ──────────────────────────────────────────────────────── */}
      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: 60, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2" style={{ fontSize: 28, animation: "spin 1s linear infinite" }} />
        </div>
      )}

      {/* ── Empty state ──────────────────────────────────────────────────── */}
      {!loading && meta && meta.results.length === 0 && (
        <div className="empty-state">
          <i className="ti ti-speakerphone" />
          <h3>No announcements yet</h3>
          <p>{category ? "No posts in this category." : "Be the first to post an announcement."}</p>
          {canPost && (
            <button className="btn btn-filled" onClick={openCreate}>Post Announcement</button>
          )}
        </div>
      )}

      {/* ── Announcement cards ───────────────────────────────────────────── */}
      {!loading && meta && meta.results.length > 0 && (
        <div className="ann-cards-list">
          {meta.results.map(ann => {
            const av = avatarColor(ann.posted_by_name);

            return (
              <div
                key={ann.id}
                className={`ann-card${ann.is_pinned ? " pinned" : ""}`}
                onClick={() => setViewTarget(ann)}
              >
                <div className="ann-card-body">
                  {/* ── Author row ─────────────────────────────────────── */}
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 12 }}>
                    <div style={{
                      width: 40, height: 40, borderRadius: "50%", flexShrink: 0,
                      background: av.bg, color: av.color,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontWeight: 700, fontSize: 14,
                    }}>
                      {initials(ann.posted_by_name)}
                    </div>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span style={{ fontWeight: 600, fontSize: 14 }}>{ann.posted_by_name}</span>
                        {ann.posted_by_role && (
                          <span style={{ fontSize: 11, color: "var(--on-variant)" }}>{ann.posted_by_role}</span>
                        )}
                        {ann.is_pinned && (
                          <span className="badge badge-warn" style={{ fontSize: 10 }}>
                            <i className="ti ti-pin" /> Pinned
                          </span>
                        )}
                        <span className={`badge ${CAT_BADGE[ann.category]}`} style={{ fontSize: 10, textTransform: "capitalize" }}>
                          {CAT_LABEL[ann.category]}
                        </span>
                        {ann.visibility !== "all" && (
                          <span className="badge badge-neutral" style={{ fontSize: 10 }}>
                            <i className={`ti ${ann.visibility === "department" ? "ti-sitemap" : "ti-building"}`} />
                            {" "}{ann.visibility === "department" ? ann.target_org_unit_name : ann.target_branch_name}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>
                        {timeAgo(ann.created_at)}
                        {ann.updated_at !== ann.created_at && " · edited"}
                      </div>
                    </div>

                    {ann.can_edit && (
                      <div style={{ display: "flex", gap: 4, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
                        <button className="btn btn-ghost btn-sm" title="Edit" onClick={() => openEdit(ann)} suppressHydrationWarning>
                          <i className="ti ti-pencil" />
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          title="Delete"
                          style={{ color: "var(--error)" }}
                          onClick={() => { setDeleteErr(null); setDeleteId(ann.id); }}
                          suppressHydrationWarning
                        >
                          <i className="ti ti-trash" />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* ── Title ─────────────────────────────────────────── */}
                  <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>
                    {ann.title}
                  </div>

                  {/* ── Body preview ─────────────────────────────────── */}
                  <div className="ann-body-preview">
                    {ann.body.length <= BODY_PREVIEW ? ann.body : ann.body.slice(0, BODY_PREVIEW) + "…"}
                  </div>
                  {ann.body.length > BODY_PREVIEW && (
                    <span className="ann-read-more">Read more</span>
                  )}

                  {/* ── Footer ────────────────────────────────────────── */}
                  <div className="ann-card-footer">
                    <button
                      onClick={e => { e.stopPropagation(); toggleReact(ann); }}
                      className={`ann-view-react-btn${ann.has_reacted ? " reacted" : ""}`}
                      suppressHydrationWarning
                    >
                      <i className={`ti ${ann.has_reacted ? "ti-heart-filled" : "ti-heart"}`} style={{ fontSize: 16 }} />
                      {ann.reactions_count > 0 && ann.reactions_count}
                    </button>

                    <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 13, color: "var(--on-variant)" }}>
                      <i className="ti ti-eye" style={{ fontSize: 15 }} />
                      {ann.views_count > 0 ? ann.views_count : "—"}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Pagination ───────────────────────────────────────────────────── */}
      {meta && meta.total_pages > 1 && (
        <div className="ann-pagination">
          <span className="ann-pagination-info">
            Page {meta.page} of {meta.total_pages}
          </span>
          <div className="ann-page-btns">
            <button className="btn btn-ghost btn-sm" disabled={meta.page <= 1} onClick={() => setPage(p => p - 1)} suppressHydrationWarning>
              <i className="ti ti-chevron-left" /> Prev
            </button>
            {Array.from({ length: meta.total_pages }, (_, i) => i + 1)
              .filter(n => Math.abs(n - meta.page) <= 2)
              .map(n => (
                <button
                  key={n}
                  className="btn btn-sm"
                  style={{
                    background: n === meta.page ? "var(--primary)" : "transparent",
                    color:      n === meta.page ? "#fff" : "var(--on-variant)",
                    border:     n === meta.page ? "none" : "1.5px solid var(--outline-v)",
                    minWidth: 32,
                  }}
                  onClick={() => setPage(n)}
                  suppressHydrationWarning
                >
                  {n}
                </button>
              ))}
            <button className="btn btn-ghost btn-sm" disabled={meta.page >= meta.total_pages} onClick={() => setPage(p => p + 1)} suppressHydrationWarning>
              Next <i className="ti ti-chevron-right" />
            </button>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          Post / Edit Modal
      ══════════════════════════════════════════════════════════════════ */}
      {showModal && (
        <Modal
          title={
            <>
              <i className="ti ti-speakerphone" />
              {editTarget ? " Edit Announcement" : " Post New Announcement"}
            </>
          }
          onClose={closeModal}
          maxWidth="min(640px, 96vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={closeModal} disabled={saving} suppressHydrationWarning>
                Cancel
              </button>
              <button className="btn btn-filled" onClick={handleSave} disabled={saving} suppressHydrationWarning>
                {saving
                  ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
                  : <><i className="ti ti-send" /> {editTarget ? "Save Changes" : "Post Announcement"}</>
                }
              </button>
            </>
          }
        >
              {saveErr && (
                <div className="alert alert-error mb-16">
                  <i className="ti ti-alert-circle" /> {saveErr}
                </div>
              )}

              {/* Title */}
              <div className="field-group">
                <label className="field-label">Title <span style={{ color: "var(--error)" }}>*</span></label>
                <input
                  ref={titleRef}
                  className={`field-input${formErrors.title ? " field-error" : ""}`}
                  placeholder="e.g. Diwali Bonus Announced"
                  value={form.title}
                  onChange={e => setField("title", e.target.value)}
                  suppressHydrationWarning
                />
                {formErrors.title && <div className="field-error-msg">{formErrors.title}</div>}
              </div>

              {/* Branch + Visibility */}
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Branch{isOrgWide && <span style={{ color: "var(--error)" }}> *</span>}</label>
                  {isOrgWide ? (
                    <select
                      className="field-input field-select"
                      value={form.target_branch}
                      onChange={e => setField("target_branch", e.target.value)}
                      disabled={form.visibility === "department"}
                    >
                      <option value="">All Branches</option>
                      {branches.map(b => <option key={b.id} value={String(b.id)}>{b.branch_name} ({b.branch_code})</option>)}
                    </select>
                  ) : (
                    <div className="field-input" style={{ background: "var(--bg)", color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 8, cursor: "default" }}>
                      <i className="ti ti-building" style={{ fontSize: 14, flexShrink: 0 }} />
                      {branches.find(b => String(b.id) === form.target_branch)?.branch_name ?? "Not assigned"}
                    </div>
                  )}
                  {form.visibility === "department" && (
                    <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
                      Not used for &quot;By Department&quot; — that reaches the department across all branches.
                    </div>
                  )}
                </div>

                <div className="field-group">
                  <label className="field-label">Visibility <span style={{ color: "var(--error)" }}>*</span></label>
                  <select
                    className="field-input field-select"
                    value={form.visibility}
                    onChange={e => setField("visibility", e.target.value as FormVisibility)}
                  >
                    {VISIBILITY_OPTIONS.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
                  </select>
                </div>
              </div>

              {/* Conditional: Department (targets an Org Unit) */}
              {form.visibility === "department" && (
                <div className="field-group">
                  <label className="field-label">Department <span style={{ color: "var(--error)" }}>*</span></label>
                  <select
                    className={`field-input field-select${formErrors.target_org_unit ? " field-error" : ""}`}
                    value={form.target_org_unit}
                    onChange={e => setField("target_org_unit", e.target.value)}
                  >
                    <option value="">Select org unit…</option>
                    {orgUnits.filter(u => u.is_active).map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
                  </select>
                  {formErrors.target_org_unit && <div className="field-error-msg">{formErrors.target_org_unit}</div>}
                </div>
              )}

              {/* Category */}
              <div className="field-group">
                <label className="field-label">Category <span style={{ color: "var(--error)" }}>*</span></label>
                <select
                  className={`field-input field-select${formErrors.category ? " field-error" : ""}`}
                  value={form.category}
                  onChange={e => setField("category", e.target.value as Category)}
                >
                  <option value="">Select category…</option>
                  {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
                {formErrors.category && <div className="field-error-msg">{formErrors.category}</div>}
              </div>

              {/* Body */}
              <div className="field-group">
                <label className="field-label">Body <span style={{ color: "var(--error)" }}>*</span></label>
                <textarea
                  className={`field-input${formErrors.body ? " field-error" : ""}`}
                  rows={6}
                  placeholder="Write your announcement…"
                  value={form.body}
                  onChange={e => setField("body", e.target.value)}
                  style={{ resize: "vertical" }}
                />
                {formErrors.body && <div className="field-error-msg">{formErrors.body}</div>}
              </div>

              {/* Checkboxes */}
              <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 14 }}>
                  <input
                    type="checkbox"
                    checked={form.is_pinned}
                    onChange={e => setField("is_pinned", e.target.checked)}
                    style={{ accentColor: "var(--primary)" }}
                    suppressHydrationWarning
                  />
                  <i className="ti ti-pin" style={{ color: "var(--warn)" }} />
                  Pin this announcement
                </label>

                {canPost && (
                  <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 14 }}>
                    <input
                      type="checkbox"
                      checked={form.send_email}
                      onChange={e => setField("send_email", e.target.checked)}
                      style={{ accentColor: "var(--primary)" }}
                      suppressHydrationWarning
                    />
                    <i className="ti ti-mail" style={{ color: "var(--info)" }} />
                    Send email notification
                  </label>
                )}
              </div>
        </Modal>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          Delete Confirm Dialog
      ══════════════════════════════════════════════════════════════════ */}
      {deleteId != null && (
        <Modal
          title={
            <span style={{ color: "var(--error)" }}>
              <i className="ti ti-trash" /> Delete Announcement
            </span>
          }
          onClose={() => { setDeleteId(null); setDeleteErr(null); }}
          closeDisabled={deleting}
          maxWidth="min(420px, 94vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => { setDeleteId(null); setDeleteErr(null); }} disabled={deleting} suppressHydrationWarning>
                Cancel
              </button>
              <button
                className="btn btn-filled"
                style={{ background: "var(--error)" }}
                onClick={handleDelete}
                disabled={deleting}
                suppressHydrationWarning
              >
                {deleting
                  ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Deleting…</>
                  : <><i className="ti ti-trash" /> Delete</>
                }
              </button>
            </>
          }
        >
          {deleteErr && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" />
              <div>{deleteErr}</div>
            </div>
          )}
          <p style={{ fontSize: 14, color: "var(--on-variant)" }}>
            This announcement will be permanently deleted and cannot be recovered.
          </p>
        </Modal>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          Announcement Detail Modal
      ══════════════════════════════════════════════════════════════════ */}
      {viewTarget && (() => {
        const live = meta?.results.find(a => a.id === viewTarget.id) ?? viewTarget;
        const av   = avatarColor(live.posted_by_name);

        return (
          <Modal
            title={
              <>
                <i className="ti ti-speakerphone" /> Announcement Details
              </>
            }
            onClose={() => setViewTarget(null)}
            maxWidth="min(640px, 96vw)"
            footer={
              <>
                {live.can_edit && (
                  <>
                    <button
                      className="btn btn-ghost"
                      style={{ color: "var(--error)" }}
                      onClick={() => { setViewTarget(null); setDeleteErr(null); setDeleteId(live.id); }}
                      suppressHydrationWarning
                    >
                      <i className="ti ti-trash" /> Delete
                    </button>
                    <button
                      className="btn btn-ghost"
                      onClick={() => { setViewTarget(null); openEdit(live); }}
                      suppressHydrationWarning
                    >
                      <i className="ti ti-pencil" /> Edit
                    </button>
                  </>
                )}
                <button className="btn btn-filled" onClick={() => setViewTarget(null)} suppressHydrationWarning>
                  Close
                </button>
              </>
            }
          >
                <div className="ann-view-author-row">
                  <div style={{
                    width: 40, height: 40, borderRadius: "50%", flexShrink: 0,
                    background: av.bg, color: av.color,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontWeight: 700, fontSize: 14,
                  }}>
                    {initials(live.posted_by_name)}
                  </div>
                  <div>
                    <div className="ann-view-name-row">
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{live.posted_by_name}</span>
                      {live.posted_by_role && <span className="ann-view-role">{live.posted_by_role}</span>}
                    </div>
                    <div className="ann-view-timestamp">
                      Posted {fullDateTime(live.created_at)}
                      {live.updated_at !== live.created_at && ` · edited ${fullDateTime(live.updated_at)}`}
                    </div>
                  </div>
                </div>

                <div className="ann-view-badges">
                  {live.is_pinned && (
                    <span className="badge badge-warn"><i className="ti ti-pin" /> Pinned</span>
                  )}
                  <span className={`badge ${CAT_BADGE[live.category]}`} style={{ textTransform: "capitalize" }}>
                    {CAT_LABEL[live.category]}
                  </span>
                  <span className="badge badge-neutral">
                    <i className={`ti ${live.visibility === "all" ? "ti-users" : live.visibility === "department" ? "ti-sitemap" : "ti-building"}`} />
                    {" "}{live.visibility === "all" ? "All Employees" : live.visibility === "department" ? live.target_org_unit_name : live.target_branch_name}
                  </span>
                </div>

                <div className="ann-view-title">{live.title}</div>
                <div className="ann-view-body">{live.body}</div>

                <div className="ann-view-stats">
                  <button
                    className={`ann-view-react-btn${live.has_reacted ? " reacted" : ""}`}
                    onClick={() => toggleReact(live)}
                    suppressHydrationWarning
                  >
                    <i className={`ti ${live.has_reacted ? "ti-heart-filled" : "ti-heart"}`} style={{ fontSize: 16 }} />
                    {live.reactions_count > 0 ? live.reactions_count : "React"}
                  </button>
                  <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 13, color: "var(--on-variant)" }}>
                    <i className="ti ti-eye" style={{ fontSize: 15 }} />
                    {live.views_count > 0 ? live.views_count : "—"} views
                  </span>
                </div>
          </Modal>
        );
      })()}

      {/* ══════════════════════════════════════════════════════════════════
          Birthday Celebration popup
      ══════════════════════════════════════════════════════════════════ */}
      {celebrateTarget && (
        <BirthdayCelebrationModal
          employee={celebrateTarget}
          onClose={() => setCelebrateTarget(null)}
        />
      )}
    </>
  );
}
