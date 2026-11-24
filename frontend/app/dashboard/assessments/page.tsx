"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission, useAnyPermission } from "@/hooks/usePermission";
import ItemsModal from "./_components/ItemsModal";
import EmployeeMyAssessments from "./_components/EmployeeMyAssessments";
import AssessmentResultsPanel from "./_components/AssessmentResultsPanel";
import AssignAssessmentModal from "./_components/AssignAssessmentModal";
import AssessmentsHeader from "./_components/AssessmentsHeader";
import AssessmentStats from "./_components/AssessmentStats";
import AssessmentToolbar from "./_components/AssessmentToolbar";
import AssessmentCard from "./_components/AssessmentCard";
import AssessmentEmptyState from "./_components/AssessmentEmptyState";
import AssessmentFormModal from "./_components/AssessmentFormModal";
import type { buildAssessmentPayload } from "@/lib/assessmentForm";
import AssessmentTemplatePicker from "./_components/AssessmentTemplatePicker";
import type { AssessmentTemplate } from "@/lib/assessmentTemplates";
import { filterAssessments, hasActiveFilters, summarize, type SortKey, type StateFilter } from "@/lib/assessmentFilters";
import {
  EMPTY, apiErr,
  type AssessmentSettings, type Assessment, type AssignEmployee,
  type EmailTemplateOption, type AssessmentForm,
} from "./_types";
import { confirmDialog } from "@/components/DialogProvider";
import { useT } from "@/hooks/useI18n";

export type { AssessmentSection, AssessmentItem, AssessmentCandidate, Assessment } from "./_types";

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AssessmentsPage() {
  const t = useT();
  // Users with assessments permissions see the HR management view;
  // everyone else (e.g. employees) sees their own assignments.
  // (The backend gates every assessments/* endpoint on assessments.*, not
  // recruitment.* — see apps/assessments/views/admin.py — so a role granted
  // only the Assessments permission set was previously bounced to the
  // employee "My Assessments" view with no way to create/edit/delete.)
  const isAdminView = useAnyPermission("assessments.view", "assessments.create", "assessments.edit", "assessments.delete");

  const canCreate = usePermission("assessments.create");
  // Assigning an assessment and managing its sections both PUT/POST through
  // endpoints gated on assessments.edit on the backend (AssignAssessmentView,
  // AssessmentItemListCreateView) — not assessments.create.
  const canEdit   = usePermission("assessments.edit");
  const canDelete = usePermission("assessments.delete");

  // Skip the admin list fetch for employees — useFetch(null) is a no-op.
  const { data, loading, error, refetch } = useFetch<{ results: Assessment[] }>(
    isAdminView ? API.assessments.list : null
  );
  const assessments = useMemo(() => data?.results ?? [], [data]);

  const { data: settingsData } = useFetch<AssessmentSettings>(
    isAdminView ? API.settings.assessmentConfig : null
  );

  const [formModal, setFormModal] = useState<{ open: boolean; target: Assessment | null }>({ open: false, target: null });
  const [form,      setForm]      = useState<AssessmentForm>(EMPTY);
  const [saving,    setSaving]    = useState(false);
  const [formErr,   setFormErr]   = useState("");

  const [deleteErr,   setDeleteErr]   = useState("");
  const [itemsFor,    setItemsFor]    = useState<Assessment | null>(null);
  const [expandedId,  setExpandedId]  = useState<string | null>(null);
  const [expandedBreakdown, setExpandedBreakdown] = useState<string | null>(null);

  function toggleResults(id: string) { setExpandedId(prev => prev === id ? null : id); }

  const [assignFor,      setAssignFor]      = useState<Assessment | null>(null);
  const [assignCids,     setAssignCids]     = useState<string[]>([]);
  const [assignSearch,   setAssignSearch]   = useState("");
  const [assigning,      setAssigning]      = useState(false);
  const [assignErr,      setAssignErr]      = useState("");
  const [assignOk,       setAssignOk]       = useState("");
  const [assignTemplate, setAssignTemplate] = useState("assessment_assigned");

  const { data: empData } = useFetch<{ results: AssignEmployee[] }>(
    assignFor ? `${API.employees.list}?page_size=500` : null
  );
  const assignCandidates = empData?.results ?? [];

  const { data: emailTemplateOptions } = useFetch<EmailTemplateOption[]>(
    assignFor ? API.assessments.emailTemplateOptions : null
  );
  const filteredCandidates = assignCandidates.filter(e =>
    assignSearch === "" ||
    e.full_name.toLowerCase().includes(assignSearch.toLowerCase()) ||
    e.email.toLowerCase().includes(assignSearch.toLowerCase()) ||
    e.employee_id.toLowerCase().includes(assignSearch.toLowerCase())
  );

  // ── Overview, search / filter / sort ───────────────────────────────────────

  const router = useRouter();
  const [search,      setSearch]      = useState("");
  const [stateFilter, setStateFilter] = useState<StateFilter>("");
  const [sort,        setSort]        = useState<SortKey>("newest");
  const totals  = useMemo(() => summarize(assessments), [assessments]);
  const visible = useMemo(() => filterAssessments(assessments, search, stateFilter, sort), [assessments, search, stateFilter, sort]);
  const hasFilters = hasActiveFilters(search, stateFilter);
  const clearFilters = () => { setSearch(""); setStateFilter(""); };
  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push("/dashboard");
  };

  // ── Assessment CRUD ────────────────────────────────────────────────────────

  function openCreate(template?: AssessmentTemplate) {
    setForm({
      ...EMPTY,
      title:           template?.formTitle ?? "",
      description:     template?.formDescription ?? "",
      pass_percentage: String(settingsData?.default_pass_percentage ?? 70),
      max_attempts:    "",
      time_limit_mins: settingsData?.time_limit_mins ? String(settingsData.time_limit_mins) : "",
    });
    setFormErr(""); setFormModal({ open: true, target: null });
  }
  function openEdit(a: Assessment) {
    setForm({
      title: a.title, description: a.description, is_active: a.is_active, is_default: a.is_default,
      pass_percentage: String(a.pass_percentage),
      max_attempts:    a.max_attempts != null ? String(a.max_attempts) : "",
      time_limit_mins: a.time_limit_mins != null ? String(a.time_limit_mins) : "",
    });
    setFormErr(""); setFormModal({ open: true, target: a });
  }

  async function saveAssessment(payload: ReturnType<typeof buildAssessmentPayload>) {
    setSaving(true); setFormErr("");
    try {
      if (formModal.target) await clientApi.put(API.assessments.detail(formModal.target.id), payload);
      else await clientApi.post(API.assessments.list, payload);
      refetch();
      setFormModal({ open: false, target: null });
    } catch (e) { setFormErr(apiErr(e)); }
    finally { setSaving(false); }
  }

  async function deleteAssessment(id: string) {
    if (!(await confirmDialog(t("Delete this assessment? This cannot be undone.")))) return;
    setDeleteErr("");
    try { await clientApi.delete(API.assessments.detail(id)); refetch(); }
    catch (e) { setDeleteErr(apiErr(e)); }
  }

  // ── Assign ─────────────────────────────────────────────────────────────────

  function openAssign(a: Assessment) {
    setAssignFor(a); setAssignCids([]); setAssignSearch(""); setAssignErr(""); setAssignOk(""); setAssignTemplate("assessment_assigned");
  }

  function toggleAssignCid(id: string) {
    setAssignCids(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }

  function toggleSelectAll() {
    setAssignCids(prev =>
      prev.length === filteredCandidates.length ? [] : filteredCandidates.map(e => e.id)
    );
  }

  async function doAssign() {
    if (assignCids.length === 0) { setAssignErr(t("Select at least one employee.")); return; }
    setAssigning(true); setAssignErr(""); setAssignOk("");
    let ok = 0;
    const errors: string[] = [];
    for (const empId of assignCids) {
      try {
        await clientApi.post(API.assessments.assign, { candidate_id: empId, assessment_id: assignFor!.id, template_name: assignTemplate });
        ok++;
      } catch (e) { errors.push(apiErr(e)); }
    }
    setSaving(false);
    if (errors.length === 0) {
      setAssignOk(ok === 1 ? t("Assigned to {count} employee successfully!", { count: ok }) : t("Assigned to {count} employees successfully!", { count: ok }));
      setAssignCids([]);
      refetch();
    } else {
      setAssignErr(t("{ok} succeeded, {failed} failed: {error}", { ok, failed: errors.length, error: errors[0] }));
    }
    setAssigning(false);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  // Employees see their own assignments, not the management view.
  if (!isAdminView) return <EmployeeMyAssessments />;

  return (
    <div className="cand-page">
      <AssessmentsHeader onBack={goBack} />

      <AssessmentStats totals={totals} isLoading={loading} />

      {assessments.length > 0 && (
        <AssessmentToolbar
          search={search} onSearch={setSearch} state={stateFilter} onState={setStateFilter} sort={sort} onSort={setSort}
          shown={visible.length} total={assessments.length} hasFilters={hasFilters} onClear={clearFilters}
        />
      )}

      {error && (
        <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{error}</div>
          <button type="button" className="btn-link" style={{ marginLeft: "auto" }} onClick={refetch}>{t("Try again")}</button>
        </div>
      )}
      {deleteErr && (
        <div className="alert alert-error" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <i className="ti ti-alert-circle" style={{ flexShrink: 0 }} />
          <div style={{ flex: 1 }}>{deleteErr}</div>
          <button onClick={() => setDeleteErr("")} style={{ background: "none", border: "none", cursor: "pointer", padding: 4, color: "inherit" }} aria-label={t("Close")}>
            <i className="ti ti-x" style={{ fontSize: 14 }} />
          </button>
        </div>
      )}

      {loading ? (
        <div className="asm-list" role="status" aria-label={t("Loading assessments")}>
          {[0, 1, 2].map(row => <div key={row} className="asm-skeleton" />)}
        </div>
      ) : visible.length === 0 ? (
        error ? null : (
          <AssessmentEmptyState isFiltered={assessments.length > 0 && hasFilters} canCreate={canCreate} onCreate={openCreate} onClear={clearFilters} />
        )
      ) : (
        <div className="asm-list">
          {visible.map(a => (
            <AssessmentCard
              key={a.id}
              assessment={a}
              canEdit={canEdit}
              canDelete={canDelete}
              isExpanded={expandedId === a.id}
              onToggleResults={() => toggleResults(a.id)}
              onSections={() => setItemsFor(a)}
              onAssign={() => openAssign(a)}
              onEdit={() => openEdit(a)}
              onDelete={() => deleteAssessment(a.id)}
            >
              <AssessmentResultsPanel
                assessment={a}
                expandedBreakdown={expandedBreakdown}
                onToggleBreakdown={id => setExpandedBreakdown(prev => prev === id ? null : id)}
              />
            </AssessmentCard>
          ))}
          {canCreate && !hasFilters && <AssessmentTemplatePicker variant="compact" onPick={openCreate} />}
        </div>
      )}

      {/* ── Assessment create / edit modal ── */}
      {formModal.open && (
        <AssessmentFormModal
          isEditing={formModal.target !== null}
          form={form}
          onChange={setForm}
          serverError={formErr}
          isSaving={saving}
          defaults={{ maxAttempts: settingsData?.max_attempts, timeLimitMins: settingsData?.time_limit_mins }}
          onSave={saveAssessment}
          onClose={() => setFormModal({ open: false, target: null })}
        />
      )}

      {/* ── Assign modal ── */}
      {assignFor && (
        <AssignAssessmentModal
          assignFor={assignFor}
          onClose={() => setAssignFor(null)}
          assignCids={assignCids}
          toggleAssignCid={toggleAssignCid}
          toggleSelectAll={toggleSelectAll}
          assignSearch={assignSearch}
          setAssignSearch={setAssignSearch}
          assignTemplate={assignTemplate}
          setAssignTemplate={setAssignTemplate}
          emailTemplateOptions={emailTemplateOptions}
          assignCandidates={assignCandidates}
          filteredCandidates={filteredCandidates}
          assigning={assigning}
          assignErr={assignErr}
          assignOk={assignOk}
          doAssign={doAssign}
        />
      )}

      {/* ── Items management modal ── */}
      {itemsFor && (
        <ItemsModal
          assessment={itemsFor}
          onClose={() => { setItemsFor(null); refetch(); }}
        />
      )}
    </div>
  );
}
