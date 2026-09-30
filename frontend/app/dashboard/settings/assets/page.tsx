"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import Modal from "@/components/Modal";
import {
  Asset, AssetCategory, AssetTypeMaster, ASSET_CONDITION_OPTIONS, ASSET_STATUS_OPTIONS,
  MAINTENANCE_OUTCOME_OPTIONS, MaintenanceOutcome, OTHER,
} from "@/types/assets";

interface PagedResponse<T> { results: T[]; count: number; page: number; page_size: number; total_pages: number }
interface Branch { id: string; branch_name: string; branch_code: string }

const PAGE_SIZE = 20;

const BLANK_FORM = {
  asset_tag: "", asset_name: "", category: "", category_other: "",
  asset_type: "", asset_type_other: "", brand: "", model: "",
  serial_number: "", purchase_date: "", purchase_price: "", vendor: "",
  warranty_start_date: "", warranty_end_date: "", branch: "", condition: "new", description: "",
};

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function AssetsSettingsPage() {
  const canCreate = usePermission("assets.create");
  const canEdit   = usePermission("assets.edit");
  const canDelete = usePermission("assets.delete");

  const [search,   setSearch]   = useState("");
  const [status,   setStatus]   = useState("");
  const [category, setCategory] = useState("");
  const [assetType, setAssetType] = useState("");
  const [branchFilter, setBranchFilter] = useState("");
  const [page,     setPage]     = useState(1);

  const params = new URLSearchParams();
  if (search)       params.set("search", search);
  if (status)       params.set("status", status);
  if (category)     params.set("category", category);
  if (assetType)    params.set("asset_type", assetType);
  if (branchFilter) params.set("branch", branchFilter);
  params.set("page", String(page));
  params.set("page_size", String(PAGE_SIZE));

  const { data, loading, refetch } = useFetch<PagedResponse<Asset>>(`${API.assets.list}?${params.toString()}`);
  const { data: branchPage } = useFetch<PagedResponse<Branch>>(API.branches.list);
  const assets   = data?.results ?? [];
  const branches = branchPage?.results ?? [];

  const [modal,   setModal]   = useState<"add" | "edit" | null>(null);
  const [form,    setForm]    = useState(BLANK_FORM);
  const [editing, setEditing] = useState<Asset | null>(null);
  const [errors,  setErrors]  = useState<Record<string, string>>({});
  const [saving,  setSaving]  = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<Asset | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // ── Category / Asset Type master data (Add/Edit form only) ──────────────
  const { data: categories, refetch: refetchCategories } = useFetch<AssetCategory[]>(API.assets.categories.list);
  const categoryList = categories ?? [];
  const selectedCategoryId = categoryList.find(c => c.name === form.category)?.id ?? null;
  const { data: types, refetch: refetchTypes } =
    useFetch<AssetTypeMaster[]>(modal ? API.assets.types.list(selectedCategoryId ?? undefined) : null);
  const typeList = types ?? [];

  // A legacy asset's category/type may not match any current master-data
  // name (predates this feature, or was renamed) — inject it as an extra
  // option instead of silently dropping it from the dropdown (spec: "handle
  // it safely instead of silently changing existing data").
  const categoryOptions = form.category && !categoryList.some(c => c.name === form.category)
    ? [...categoryList, { id: -1, name: form.category, is_active: true, created_at: "", updated_at: "" }]
    : categoryList;
  const typeOptions = form.asset_type && !typeList.some(t => t.name === form.asset_type)
    ? [...typeList, { id: -1, name: form.asset_type, category: -1, category_name: "", is_active: true, created_at: "", updated_at: "" }]
    : typeList;

  const [addCategoryOpen, setAddCategoryOpen] = useState(false);
  const [addCategoryName, setAddCategoryName] = useState("");
  const [addCategoryError, setAddCategoryError] = useState<string | null>(null);
  const [addCategorySaving, setAddCategorySaving] = useState(false);

  const [addTypeOpen, setAddTypeOpen] = useState(false);
  const [addTypeName, setAddTypeName] = useState("");
  const [addTypeError, setAddTypeError] = useState<string | null>(null);
  const [addTypeSaving, setAddTypeSaving] = useState(false);

  function openAdd() {
    setForm(BLANK_FORM);
    setErrors({});
    setSaveError(null);
    setEditing(null);
    setModal("add");
  }

  function openEdit(asset: Asset) {
    setForm({
      asset_tag: asset.asset_tag, asset_name: asset.asset_name, category: asset.category,
      category_other: asset.category_other ?? "",
      asset_type: asset.asset_type, asset_type_other: asset.asset_type_other ?? "",
      brand: asset.brand, model: asset.model,
      serial_number: asset.serial_number ?? "", purchase_date: asset.purchase_date ?? "",
      purchase_price: asset.purchase_price ?? "", vendor: asset.vendor,
      warranty_start_date: asset.warranty_start_date ?? "", warranty_end_date: asset.warranty_end_date ?? "",
      branch: String(asset.branch), condition: asset.condition, description: asset.description,
    });
    setErrors({});
    setSaveError(null);
    setEditing(asset);
    setModal("edit");
  }

  function clearFieldError(field: string) {
    setErrors(prev => { const next = { ...prev }; delete next[field]; return next; });
  }

  // Changing category invalidates whatever type was selected under the
  // PREVIOUS category — cleared here rather than left stale/mismatched.
  function changeCategory(name: string) {
    clearFieldError("category");
    setForm(p => ({
      ...p, category: name, category_other: name === OTHER ? p.category_other : "",
      asset_type: "", asset_type_other: "",
    }));
  }

  function changeAssetType(name: string) {
    clearFieldError("asset_type");
    setForm(p => ({ ...p, asset_type: name, asset_type_other: name === OTHER ? p.asset_type_other : "" }));
  }

  async function submitAddCategory() {
    const name = addCategoryName.trim();
    if (!name) { setAddCategoryError("Category name is required."); return; }
    setAddCategorySaving(true);
    setAddCategoryError(null);
    try {
      const res = await clientApi.post(API.assets.categories.list, { name });
      await refetchCategories();
      setForm(p => ({ ...p, category: res.data.data.name, category_other: "", asset_type: "", asset_type_other: "" }));
      setAddCategoryOpen(false);
      setAddCategoryName("");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setAddCategoryError(msg ?? "Failed to add category.");
    } finally {
      setAddCategorySaving(false);
    }
  }

  async function submitAddType() {
    const name = addTypeName.trim();
    if (!name) { setAddTypeError("Asset Type name is required."); return; }
    if (!selectedCategoryId) { setAddTypeError("Select a category first."); return; }
    setAddTypeSaving(true);
    setAddTypeError(null);
    try {
      const res = await clientApi.post(API.assets.types.list(), { name, category: selectedCategoryId });
      await refetchTypes();
      setForm(p => ({ ...p, asset_type: res.data.data.name, asset_type_other: "" }));
      setAddTypeOpen(false);
      setAddTypeName("");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setAddTypeError(msg ?? "Failed to add asset type.");
    } finally {
      setAddTypeSaving(false);
    }
  }

  async function save() {
    setSaving(true);
    setSaveError(null);
    setErrors({});
    const payload: Record<string, unknown> = {
      ...form,
      purchase_price: form.purchase_price || null,
      purchase_date: form.purchase_date || null,
      warranty_start_date: form.warranty_start_date || null,
      warranty_end_date: form.warranty_end_date || null,
      serial_number: form.serial_number || null,
    };
    try {
      if (modal === "add") {
        await clientApi.post(API.assets.list, payload);
      } else if (editing) {
        await clientApi.put(API.assets.detail(editing.id), payload);
      }
      setModal(null);
      refetch();
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { message?: string; data?: Record<string, string[]> } } })?.response?.data;
      if (resp?.data) {
        const fieldErrors: Record<string, string> = {};
        for (const [field, msgs] of Object.entries(resp.data)) {
          fieldErrors[field] = Array.isArray(msgs) ? msgs[0] : String(msgs);
        }
        setErrors(fieldErrors);
      }
      setSaveError(resp?.message ?? "Failed to save asset. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await clientApi.delete(API.assets.detail(deleteTarget.id));
      setDeleteTarget(null);
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setDeleteError(msg ?? "Failed to delete asset.");
    } finally {
      setDeleting(false);
    }
  }

  // ── Send to Maintenance ──────────────────────────────────────────────
  const [maintTarget, setMaintTarget] = useState<Asset | null>(null);
  const [maintForm, setMaintForm] = useState({
    maintenance_start_date: "", issue: "", expected_completion_date: "",
    vendor: "", estimated_cost: "", notes: "",
  });
  const [maintError, setMaintError] = useState<string | null>(null);
  const [maintSaving, setMaintSaving] = useState(false);

  function openSendToMaintenance(asset: Asset) {
    setMaintForm({
      maintenance_start_date: new Date().toISOString().split("T")[0],
      issue: "", expected_completion_date: "", vendor: "", estimated_cost: "", notes: "",
    });
    setMaintError(null);
    setMaintTarget(asset);
  }

  async function submitSendToMaintenance() {
    if (!maintTarget) return;
    if (!maintForm.issue.trim()) { setMaintError("Issue / Reason is required."); return; }
    setMaintSaving(true);
    setMaintError(null);
    try {
      await clientApi.post(API.assets.sendToMaintenance(maintTarget.id), {
        ...maintForm,
        expected_completion_date: maintForm.expected_completion_date || null,
        estimated_cost: maintForm.estimated_cost || null,
      });
      setMaintTarget(null);
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setMaintError(msg ?? "Failed to send asset to maintenance.");
    } finally {
      setMaintSaving(false);
    }
  }

  // ── Complete Maintenance ─────────────────────────────────────────────
  const [completeTarget, setCompleteTarget] = useState<Asset | null>(null);
  const [completeForm, setCompleteForm] = useState({
    completed_date: "", outcome: "repaired" as MaintenanceOutcome,
    maintenance_notes: "", actual_cost: "", resulting_condition: "good",
  });
  const [completeError, setCompleteError] = useState<string | null>(null);
  const [completeSaving, setCompleteSaving] = useState(false);

  function openCompleteMaintenance(asset: Asset) {
    setCompleteForm({
      completed_date: new Date().toISOString().split("T")[0], outcome: "repaired",
      maintenance_notes: "", actual_cost: "", resulting_condition: "good",
    });
    setCompleteError(null);
    setCompleteTarget(asset);
  }

  async function submitCompleteMaintenance() {
    if (!completeTarget?.active_maintenance) return;
    if (!completeForm.maintenance_notes.trim()) { setCompleteError("Repair/Maintenance notes are required."); return; }
    setCompleteSaving(true);
    setCompleteError(null);
    try {
      await clientApi.post(API.assets.completeMaintenance(completeTarget.active_maintenance.id), {
        ...completeForm,
        actual_cost: completeForm.actual_cost || null,
        resulting_condition: completeForm.outcome === "repaired" ? completeForm.resulting_condition : undefined,
      });
      setCompleteTarget(null);
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setCompleteError(msg ?? "Failed to complete maintenance.");
    } finally {
      setCompleteSaving(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Asset Management</div>
          <div className="page-sub">Track company equipment and who it&apos;s assigned to</div>
        </div>
        {canCreate && (
          <div className="page-actions">
            <button className="btn btn-filled btn-sm" onClick={openAdd}>
              <i className="ti ti-plus" /> Add Asset
            </button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 20 }}>
        <input
          className="field-input" style={{ maxWidth: 260 }}
          placeholder="Search tag, name, serial number…"
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
        />
        <select className="field-input" style={{ maxWidth: 160 }} value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All Statuses</option>
          {ASSET_STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <input
          className="field-input" style={{ maxWidth: 150 }} placeholder="Category"
          value={category} onChange={e => { setCategory(e.target.value); setPage(1); }}
        />
        <input
          className="field-input" style={{ maxWidth: 150 }} placeholder="Asset Type"
          value={assetType} onChange={e => { setAssetType(e.target.value); setPage(1); }}
        />
        <select className="field-input" style={{ maxWidth: 180 }} value={branchFilter} onChange={e => { setBranchFilter(e.target.value); setPage(1); }}>
          <option value="">All Branches</option>
          {branches.map(b => <option key={b.id} value={b.id}>{b.branch_name}</option>)}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ padding: 40, textAlign: "center", color: "var(--on-variant)" }}><Spin /></div>
      ) : assets.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: "var(--on-variant)", border: "1.5px dashed var(--outline-v)", borderRadius: "var(--radius)" }}>
          <i className="ti ti-package" style={{ fontSize: 32, display: "block", marginBottom: 8 }} />
          No assets found.
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Asset Tag</th>
                <th>Name</th>
                <th>Category</th>
                <th>Type</th>
                <th>Branch</th>
                <th>Status</th>
                <th>Condition</th>
                {(canEdit || canDelete) && <th style={{ textAlign: "right" }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {assets.map(a => (
                <tr key={a.id}>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>{a.asset_tag}</td>
                  <td>{a.asset_name}</td>
                  <td>{a.category === OTHER && a.category_other ? `Other (${a.category_other})` : a.category}</td>
                  <td>{a.asset_type === OTHER && a.asset_type_other ? `Other (${a.asset_type_other})` : a.asset_type}</td>
                  <td>{a.branch_name}</td>
                  <td><span className="badge badge-info">{a.status_display}</span></td>
                  <td>{a.condition_display}</td>
                  {(canEdit || canDelete) && (
                    <td style={{ textAlign: "right" }}>
                      {canEdit && a.status === "damaged" && (
                        <button className="btn btn-ghost btn-sm" title="Send to Maintenance" onClick={() => openSendToMaintenance(a)}>
                          <i className="ti ti-tool" />
                        </button>
                      )}
                      {canEdit && a.status === "under_repair" && a.active_maintenance && (
                        <button className="btn btn-ghost btn-sm" title="Complete Maintenance" onClick={() => openCompleteMaintenance(a)}>
                          <i className="ti ti-circle-check" />
                        </button>
                      )}
                      {canEdit && (
                        <button className="btn btn-ghost btn-sm" onClick={() => openEdit(a)}>
                          <i className="ti ti-edit" />
                        </button>
                      )}
                      {canDelete && (
                        <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} onClick={() => setDeleteTarget(a)}>
                          <i className="ti ti-trash" />
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {data && data.total_pages > 1 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, marginTop: 14 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {data.page} of {data.total_pages}</span>
              <button className="btn btn-ghost btn-sm" disabled={page >= data.total_pages} onClick={() => setPage(p => p + 1)}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Add/Edit modal */}
      {modal && (
        <Modal
          title={<><i className="ti ti-package" style={{ marginRight: 8 }} />{modal === "add" ? "Add Asset" : `Edit: ${editing?.asset_tag}`}</>}
          onClose={() => setModal(null)}
          maxWidth={560}
          scrollBody
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setModal(null)} disabled={saving}>Cancel</button>
              <button className="btn btn-filled" onClick={save} disabled={saving}>
                {saving ? <><Spin />&nbsp;Saving…</> : modal === "add" ? "Create Asset" : "Save Changes"}
              </button>
            </>
          }
        >
          {saveError && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {saveError}</div>}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div className="field-group mb-16">
              <label className="field-label">Asset Tag *</label>
              <input
                className={`field-input${errors.asset_tag ? " field-error" : ""}`}
                value={form.asset_tag}
                onChange={e => { clearFieldError("asset_tag"); setForm(p => ({ ...p, asset_tag: e.target.value })); }}
                placeholder="e.g. LAP-001"
              />
              {errors.asset_tag && <p className="field-error-msg">{errors.asset_tag}</p>}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Asset Name *</label>
              <input
                className={`field-input${errors.asset_name ? " field-error" : ""}`}
                value={form.asset_name}
                onChange={e => { clearFieldError("asset_name"); setForm(p => ({ ...p, asset_name: e.target.value })); }}
                placeholder="e.g. Dell Latitude 5420"
              />
              {errors.asset_name && <p className="field-error-msg">{errors.asset_name}</p>}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Category *</label>
              <div style={{ display: "flex", gap: 6 }}>
                <select
                  className={`field-input${errors.category ? " field-error" : ""}`}
                  value={form.category}
                  onChange={e => changeCategory(e.target.value)}
                >
                  <option value="">Select category…</option>
                  {categoryOptions.map(c => <option key={c.id} value={c.name}>{c.name}</option>)}
                </select>
                <button type="button" className="btn btn-ghost btn-sm" title="Add Category"
                  onClick={() => { setAddCategoryError(null); setAddCategoryName(""); setAddCategoryOpen(true); }}>
                  <i className="ti ti-plus" />
                </button>
              </div>
              {errors.category && <p className="field-error-msg">{errors.category}</p>}
              {form.category === OTHER && (
                <div style={{ marginTop: 8 }}>
                  <input
                    className={`field-input${errors.category_other ? " field-error" : ""}`}
                    value={form.category_other}
                    onChange={e => { clearFieldError("category_other"); setForm(p => ({ ...p, category_other: e.target.value })); }}
                    placeholder="Other category — enter a name"
                  />
                  {errors.category_other && <p className="field-error-msg">{errors.category_other}</p>}
                </div>
              )}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Asset Type *</label>
              <div style={{ display: "flex", gap: 6 }}>
                <select
                  className={`field-input${errors.asset_type ? " field-error" : ""}`}
                  value={form.asset_type}
                  disabled={!form.category}
                  onChange={e => changeAssetType(e.target.value)}
                >
                  <option value="">{form.category ? "Select asset type…" : "Select a category first"}</option>
                  {typeOptions.map(t => <option key={t.id} value={t.name}>{t.name}</option>)}
                </select>
                <button type="button" className="btn btn-ghost btn-sm" title="Add Asset Type"
                  disabled={!selectedCategoryId}
                  onClick={() => { setAddTypeError(null); setAddTypeName(""); setAddTypeOpen(true); }}>
                  <i className="ti ti-plus" />
                </button>
              </div>
              {errors.asset_type && <p className="field-error-msg">{errors.asset_type}</p>}
              {form.asset_type === OTHER && (
                <div style={{ marginTop: 8 }}>
                  <input
                    className={`field-input${errors.asset_type_other ? " field-error" : ""}`}
                    value={form.asset_type_other}
                    onChange={e => { clearFieldError("asset_type_other"); setForm(p => ({ ...p, asset_type_other: e.target.value })); }}
                    placeholder="Other asset type — enter a name"
                  />
                  {errors.asset_type_other && <p className="field-error-msg">{errors.asset_type_other}</p>}
                </div>
              )}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Brand</label>
              <input className="field-input" value={form.brand} onChange={e => setForm(p => ({ ...p, brand: e.target.value }))} />
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Model</label>
              <input className="field-input" value={form.model} onChange={e => setForm(p => ({ ...p, model: e.target.value }))} />
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Serial Number</label>
              <input
                className={`field-input${errors.serial_number ? " field-error" : ""}`}
                value={form.serial_number}
                onChange={e => { clearFieldError("serial_number"); setForm(p => ({ ...p, serial_number: e.target.value })); }}
              />
              {errors.serial_number && <p className="field-error-msg">{errors.serial_number}</p>}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Branch *</label>
              <select
                className={`field-input${errors.branch ? " field-error" : ""}`}
                value={form.branch}
                onChange={e => { clearFieldError("branch"); setForm(p => ({ ...p, branch: e.target.value })); }}
              >
                <option value="">Select branch…</option>
                {branches.map(b => <option key={b.id} value={b.id}>{b.branch_name}</option>)}
              </select>
              {errors.branch && <p className="field-error-msg">{errors.branch}</p>}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Purchase Date</label>
              <input type="date" className="field-input" value={form.purchase_date} onChange={e => setForm(p => ({ ...p, purchase_date: e.target.value }))} />
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Purchase Price</label>
              <input
                type="number" min="0" step="0.01"
                className={`field-input${errors.purchase_price ? " field-error" : ""}`}
                value={form.purchase_price}
                onChange={e => { clearFieldError("purchase_price"); setForm(p => ({ ...p, purchase_price: e.target.value })); }}
              />
              {errors.purchase_price && <p className="field-error-msg">{errors.purchase_price}</p>}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Vendor</label>
              <input className="field-input" value={form.vendor} onChange={e => setForm(p => ({ ...p, vendor: e.target.value }))} />
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Condition</label>
              <select className="field-input" value={form.condition} onChange={e => setForm(p => ({ ...p, condition: e.target.value }))}>
                {ASSET_CONDITION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Warranty Start</label>
              <input type="date" className="field-input" value={form.warranty_start_date} onChange={e => setForm(p => ({ ...p, warranty_start_date: e.target.value }))} />
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Warranty End</label>
              <input
                type="date"
                className={`field-input${errors.warranty_end_date ? " field-error" : ""}`}
                value={form.warranty_end_date}
                onChange={e => { clearFieldError("warranty_end_date"); setForm(p => ({ ...p, warranty_end_date: e.target.value })); }}
              />
              {errors.warranty_end_date && <p className="field-error-msg">{errors.warranty_end_date}</p>}
            </div>
          </div>

          <div className="field-group mb-16">
            <label className="field-label">Description / Remarks</label>
            <textarea
              className="field-input" style={{ minHeight: 70 }}
              value={form.description}
              onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
            />
          </div>
        </Modal>
      )}

      {/* Quick-add Category */}
      {addCategoryOpen && (
        <Modal
          title="Add Category"
          onClose={() => setAddCategoryOpen(false)}
          maxWidth={380}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setAddCategoryOpen(false)} disabled={addCategorySaving}>Cancel</button>
              <button className="btn btn-filled" onClick={submitAddCategory} disabled={addCategorySaving}>
                {addCategorySaving ? <><Spin />&nbsp;Adding…</> : "Add Category"}
              </button>
            </>
          }
        >
          {addCategoryError && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {addCategoryError}</div>}
          <div className="field-group">
            <label className="field-label">Category Name *</label>
            <input className="field-input" value={addCategoryName} onChange={e => setAddCategoryName(e.target.value)} autoFocus />
          </div>
        </Modal>
      )}

      {/* Quick-add Asset Type */}
      {addTypeOpen && (
        <Modal
          title="Add Asset Type"
          onClose={() => setAddTypeOpen(false)}
          maxWidth={380}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setAddTypeOpen(false)} disabled={addTypeSaving}>Cancel</button>
              <button className="btn btn-filled" onClick={submitAddType} disabled={addTypeSaving}>
                {addTypeSaving ? <><Spin />&nbsp;Adding…</> : "Add Asset Type"}
              </button>
            </>
          }
        >
          {addTypeError && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {addTypeError}</div>}
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 12 }}>
            Category: <strong>{form.category}</strong>
          </div>
          <div className="field-group">
            <label className="field-label">Asset Type Name *</label>
            <input className="field-input" value={addTypeName} onChange={e => setAddTypeName(e.target.value)} autoFocus />
          </div>
        </Modal>
      )}

      {/* Send to Maintenance */}
      {maintTarget && (
        <Modal
          title={<><i className="ti ti-tool" style={{ marginRight: 8 }} />Send to Maintenance — {maintTarget.asset_tag}</>}
          onClose={() => setMaintTarget(null)}
          maxWidth={460}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setMaintTarget(null)} disabled={maintSaving}>Cancel</button>
              <button className="btn btn-filled" onClick={submitSendToMaintenance} disabled={maintSaving}>
                {maintSaving ? <><Spin />&nbsp;Sending…</> : "Send to Maintenance"}
              </button>
            </>
          }
        >
          {maintError && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {maintError}</div>}
          <div className="field-group mb-16">
            <label className="field-label">Maintenance Start Date *</label>
            <input type="date" className="field-input" value={maintForm.maintenance_start_date}
              onChange={e => setMaintForm(p => ({ ...p, maintenance_start_date: e.target.value }))} />
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Issue / Reason *</label>
            <textarea className="field-input" style={{ minHeight: 60 }} value={maintForm.issue}
              onChange={e => setMaintForm(p => ({ ...p, issue: e.target.value }))} placeholder="What's wrong with it?" />
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Expected Completion Date <span style={{ color: "var(--outline)", fontWeight: 400 }}>(optional)</span></label>
            <input type="date" className="field-input" value={maintForm.expected_completion_date}
              onChange={e => setMaintForm(p => ({ ...p, expected_completion_date: e.target.value }))} />
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Vendor / Service Center <span style={{ color: "var(--outline)", fontWeight: 400 }}>(optional)</span></label>
            <input className="field-input" value={maintForm.vendor} onChange={e => setMaintForm(p => ({ ...p, vendor: e.target.value }))} />
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Estimated Cost <span style={{ color: "var(--outline)", fontWeight: 400 }}>(optional)</span></label>
            <input type="number" min="0" step="0.01" className="field-input" value={maintForm.estimated_cost}
              onChange={e => setMaintForm(p => ({ ...p, estimated_cost: e.target.value }))} />
          </div>
          <div className="field-group">
            <label className="field-label">Notes <span style={{ color: "var(--outline)", fontWeight: 400 }}>(optional)</span></label>
            <textarea className="field-input" value={maintForm.notes} onChange={e => setMaintForm(p => ({ ...p, notes: e.target.value }))} />
          </div>
        </Modal>
      )}

      {/* Complete Maintenance */}
      {completeTarget && (
        <Modal
          title={<><i className="ti ti-circle-check" style={{ marginRight: 8 }} />Complete Maintenance — {completeTarget.asset_tag}</>}
          onClose={() => setCompleteTarget(null)}
          maxWidth={460}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setCompleteTarget(null)} disabled={completeSaving}>Cancel</button>
              <button className="btn btn-filled" onClick={submitCompleteMaintenance} disabled={completeSaving}>
                {completeSaving ? <><Spin />&nbsp;Saving…</> : "Complete Maintenance"}
              </button>
            </>
          }
        >
          {completeError && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {completeError}</div>}
          {completeTarget.active_maintenance && (
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 16, padding: "8px 12px", background: "var(--bg-low)", borderRadius: "var(--radius)" }}>
              Issue: <strong style={{ color: "var(--on-bg)" }}>{completeTarget.active_maintenance.issue}</strong>
            </div>
          )}
          <div className="field-group mb-16">
            <label className="field-label">Completed Date *</label>
            <input type="date" className="field-input" value={completeForm.completed_date}
              onChange={e => setCompleteForm(p => ({ ...p, completed_date: e.target.value }))} />
          </div>
          <div className="field-group mb-16">
            <label className="field-label">Outcome *</label>
            <select className="field-input" value={completeForm.outcome}
              onChange={e => setCompleteForm(p => ({ ...p, outcome: e.target.value as MaintenanceOutcome }))}>
              {MAINTENANCE_OUTCOME_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          {completeForm.outcome === "repaired" && (
            <div className="field-group mb-16">
              <label className="field-label">Resulting Condition</label>
              <select className="field-input" value={completeForm.resulting_condition}
                onChange={e => setCompleteForm(p => ({ ...p, resulting_condition: e.target.value }))}>
                {ASSET_CONDITION_OPTIONS.filter(o => o.value !== "damaged").map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          )}
          <div className="field-group mb-16">
            <label className="field-label">Repair / Maintenance Notes *</label>
            <textarea className="field-input" style={{ minHeight: 60 }} value={completeForm.maintenance_notes}
              onChange={e => setCompleteForm(p => ({ ...p, maintenance_notes: e.target.value }))} />
          </div>
          <div className="field-group">
            <label className="field-label">Actual Cost <span style={{ color: "var(--outline)", fontWeight: 400 }}>(optional)</span></label>
            <input type="number" min="0" step="0.01" className="field-input" value={completeForm.actual_cost}
              onChange={e => setCompleteForm(p => ({ ...p, actual_cost: e.target.value }))} />
          </div>
        </Modal>
      )}

      {/* Delete confirm */}
      {deleteTarget && (
        <div className="modal-overlay open" style={{ zIndex: 1010 }}>
          <div className="modal" style={{ maxWidth: "420px" }}>
            <div className="modal-header">
              <div className="modal-title">
                <i className="ti ti-alert-triangle" style={{ marginRight: 8, color: "var(--error)" }} />
                Delete Asset?
              </div>
              <button className="modal-close" onClick={() => setDeleteTarget(null)} disabled={deleting}>
                <i className="ti ti-x" />
              </button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: 14, color: "var(--on-variant)", lineHeight: 1.6 }}>
                Are you sure you want to delete <strong>{deleteTarget.asset_tag} — {deleteTarget.asset_name}</strong>? This action cannot be undone.
              </p>
              {deleteError && <div className="alert alert-error" style={{ marginTop: 12 }}><i className="ti ti-alert-circle" /> {deleteError}</div>}
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setDeleteTarget(null)} disabled={deleting}>Cancel</button>
              <button className="btn btn-filled" style={{ background: "var(--error)" }} onClick={confirmDelete} disabled={deleting}>
                {deleting ? <><Spin />&nbsp;Deleting…</> : "Yes, Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
