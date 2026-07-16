"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

type ExpenseCategory = "travel" | "meals" | "equipment" | "other";

interface FormState {
  title:       string;
  amount:      string;
  category:    ExpenseCategory | "";
  date:        string;
  description: string;
}

interface Props {
  onClose: () => void;
  onSaved: () => void;
}

const CATEGORIES: { value: ExpenseCategory; label: string; icon: string }[] = [
  { value: "travel",    label: "Travel",    icon: "ti-plane-departure"        },
  { value: "meals",     label: "Meals",     icon: "ti-tools-kitchen-2"        },
  { value: "equipment", label: "Equipment", icon: "ti-device-desktop"         },
  { value: "other",     label: "Other",     icon: "ti-dots-circle-horizontal" },
];

const EMPTY: FormState = { title: "", amount: "", category: "", date: "", description: "" };

type FormErrors = Partial<Record<keyof FormState | "receipt" | "submit", string>>;

export default function ExpenseFormModal({ onClose, onSaved }: Props) {
  const [form,         setForm]         = useState<FormState>(EMPTY);
  const [errors,       setErrors]       = useState<FormErrors>({});
  const [receiptFiles, setReceiptFiles] = useState<File[]>([]);
  const [submitting,   setSubmitting]   = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
    setErrors(prev => ({ ...prev, [key]: undefined }));
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    if (!selected.length) return;
    const allowed = ["image/jpeg", "image/png", "application/pdf"];
    for (const file of selected) {
      if (file.size > 5 * 1024 * 1024) {
        setErrors(prev => ({ ...prev, receipt: `"${file.name}" exceeds 5 MB.` }));
        return;
      }
      if (!allowed.includes(file.type)) {
        setErrors(prev => ({ ...prev, receipt: `"${file.name}" must be PDF, JPG, or PNG.` }));
        return;
      }
    }
    setReceiptFiles(prev => [...prev, ...selected]);
    setErrors(prev => ({ ...prev, receipt: undefined }));
    e.target.value = "";
  }

  function removeReceipt(index: number) {
    setReceiptFiles(prev => prev.filter((_, i) => i !== index));
  }

  function validate(): boolean {
    const errs: FormErrors = {};
    if (!form.title.trim())            errs.title    = "Expense title is required.";
    if (!form.amount)                  errs.amount   = "Amount is required.";
    else if (Number(form.amount) <= 0) errs.amount   = "Amount must be greater than zero.";
    if (!form.category)                errs.category = "Please select a category.";
    if (!form.date)                    errs.date     = "Date is required.";
    if (receiptFiles.length === 0)     errs.receipt  = "At least one receipt is required.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("title",        form.title.trim());
      formData.append("amount",       form.amount);
      formData.append("category",     form.category);
      formData.append("expense_date", form.date);
      formData.append("description",  form.description.trim());
      for (const file of receiptFiles) {
        formData.append("receipts", file);
      }
      await clientApi.post(API.expenses.list, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onSaved();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })
          ?.response?.data?.message ?? "Failed to submit expense. Please try again.";
      setErrors(prev => ({ ...prev, submit: msg }));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ width: "min(560px, 95vw)", maxHeight: "92vh", overflowY: "auto" }}>
        <div className="modal-header">
          <div className="modal-title">
            <i className="ti ti-wallet" style={{ marginRight: 8 }} />
            Submit New Expense
          </div>
          <button className="modal-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          {errors.submit && (
            <div className="alert alert-error" style={{ marginBottom: 16 }}>
              <i className="ti ti-alert-circle" /><div>{errors.submit}</div>
            </div>
          )}

          {/* Title */}
          <div className="field-group mb-16">
            <label className="field-label">
              Expense Title <span style={{ color: "var(--error)" }}>*</span>
            </label>
            <input
              type="text"
              className={`field-input${errors.title ? " field-error" : ""}`}
              placeholder="e.g. Client visit to Mumbai"
              value={form.title}
              onChange={e => setField("title", e.target.value)}
            />
            {errors.title && <p className="field-error-msg">{errors.title}</p>}
          </div>

          {/* Amount + Category */}
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">
                Amount (₹) <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <input
                type="number"
                min="1"
                className={`field-input${errors.amount ? " field-error" : ""}`}
                placeholder="0.00"
                value={form.amount}
                onChange={e => setField("amount", e.target.value)}
              />
              {errors.amount && <p className="field-error-msg">{errors.amount}</p>}
            </div>
            <div className="field-group">
              <label className="field-label">
                Category <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <select
                className={`field-input${errors.category ? " field-error" : ""}`}
                value={form.category}
                onChange={e => setField("category", e.target.value as ExpenseCategory | "")}
              >
                <option value="">Select category…</option>
                {CATEGORIES.map(c => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
              {errors.category && <p className="field-error-msg">{errors.category}</p>}
            </div>
          </div>

          {/* Date */}
          <div className="field-group mb-16">
            <label className="field-label">
              Date <span style={{ color: "var(--error)" }}>*</span>
            </label>
            <input
              type="date"
              className={`field-input${errors.date ? " field-error" : ""}`}
              value={form.date}
              onChange={e => setField("date", e.target.value)}
            />
            {errors.date && <p className="field-error-msg">{errors.date}</p>}
          </div>

          {/* Description */}
          <div className="field-group mb-16">
            <label className="field-label">Description</label>
            <textarea
              className="field-input"
              rows={3}
              placeholder="Optional notes about this expense…"
              value={form.description}
              onChange={e => setField("description", e.target.value)}
              style={{ resize: "vertical" }}
            />
          </div>

          {/* Receipt upload — mandatory, multiple */}
          <div className="field-group mb-16">
            <label className="field-label">
              Receipts <span style={{ color: "var(--error)" }}>*</span>
            </label>

            {/* Selected files list */}
            {receiptFiles.length > 0 && (
              <div style={{ marginBottom: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                {receiptFiles.map((file, idx) => (
                  <div key={idx} style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "6px 10px", borderRadius: 6,
                    background: "var(--bg-high)", fontSize: 13,
                  }}>
                    <i className="ti ti-file" style={{ color: "var(--primary)" }} />
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {file.name}
                    </span>
                    <span style={{ color: "var(--on-variant)", fontSize: 11 }}>
                      {(file.size / 1024).toFixed(0)} KB
                    </span>
                    <button
                      type="button"
                      onClick={() => removeReceipt(idx)}
                      style={{ background: "none", border: "none", cursor: "pointer", color: "var(--error)", padding: 2 }}
                    >
                      <i className="ti ti-x" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div
              className={`upload-zone${errors.receipt ? " field-error" : ""}`}
              style={{ cursor: "pointer" }}
              onClick={() => fileInputRef.current?.click()}
            >
              <i className="ti ti-file-plus" />
              <p>{receiptFiles.length > 0 ? "Add more receipts" : "Click to upload receipts"}</p>
              <small>PDF, JPG, PNG up to 5 MB each — at least one required</small>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              multiple
              style={{ display: "none" }}
              onChange={handleFileChange}
            />
            {errors.receipt && <p className="field-error-msg">{errors.receipt}</p>}
          </div>

          {/* Info banner */}
          <div className="alert alert-info" style={{ marginBottom: 0 }}>
            <i className="ti ti-info-circle" />
            <span>
              Your expense will be sent for approval. Approved expenses are reimbursed in the next payroll cycle.
            </span>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting}>
            {submitting
              ? <><i className="ti ti-loader-2 spin" /> Submitting…</>
              : <><i className="ti ti-send" /> Submit Expense</>
            }
          </button>
        </div>
      </div>
    </div>
  );
}
