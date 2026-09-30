"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import Modal from "@/components/Modal";
import {
  Asset, ASSET_CONDITION_OPTIONS, ASSET_STATUS_OPTIONS,
} from "@/types/assets";

interface PagedResponse<T> { results: T[]; count: number; page: number; page_size: number; total_pages: number }
interface Branch { id: string; branch_name: string; branch_code: string }

const PAGE_SIZE = 20;

const BLANK_FORM = {
  asset_tag: "", asset_name: "", category: "", asset_type: "", brand: "", model: "",
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
      asset_type: asset.asset_type, brand: asset.brand, model: asset.model,
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
                  <td>{a.category}</td>
                  <td>{a.asset_type}</td>
                  <td>{a.branch_name}</td>
                  <td><span className="badge badge-info">{a.status_display}</span></td>
                  <td>{a.condition_display}</td>
                  {(canEdit || canDelete) && (
                    <td style={{ textAlign: "right" }}>
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
              <input
                className={`field-input${errors.category ? " field-error" : ""}`}
                value={form.category}
                onChange={e => { clearFieldError("category"); setForm(p => ({ ...p, category: e.target.value })); }}
                placeholder="e.g. Laptop"
              />
              {errors.category && <p className="field-error-msg">{errors.category}</p>}
            </div>
            <div className="field-group mb-16">
              <label className="field-label">Asset Type *</label>
              <input
                className={`field-input${errors.asset_type ? " field-error" : ""}`}
                value={form.asset_type}
                onChange={e => { clearFieldError("asset_type"); setForm(p => ({ ...p, asset_type: e.target.value })); }}
                placeholder="e.g. Electronics"
              />
              {errors.asset_type && <p className="field-error-msg">{errors.asset_type}</p>}
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
