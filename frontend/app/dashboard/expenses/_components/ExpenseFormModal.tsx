"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { formatDateSlash } from "@/lib/formatDate";
import { currentFinancialYearStart, financialYearLabel } from "@/app/dashboard/my-payslip/_components/types";
import RequestModal from "@/components/RequestModal";
import DateInput from "@/components/shared/DateInput";

type ExpenseCategory = "travel" | "meals" | "equipment" | "other";

interface FormState {
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

const CATEGORY_LABEL: Record<ExpenseCategory, string> = Object.fromEntries(
  CATEGORIES.map(c => [c.value, c.label]),
) as Record<ExpenseCategory, string>;

// A bill may be dated up to this many months before the current financial year starts
// (the backend enforces the same window — EXPENSE_BACKDATE_MONTHS in hrms/serializers.py).
const BACKDATE_MONTHS = 4;
const RECEIPT_PREVIEW_LIFETIME_MS = 60_000;

function toIsoDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/** Earliest/latest allowed expense date for the company's current financial year, plus a label for the hint. */
function getExpenseDateWindow(startMonthName: string) {
  const fyStart = currentFinancialYearStart(startMonthName);
  const earliest = new Date(fyStart.getFullYear(), fyStart.getMonth() - BACKDATE_MONTHS, 1);
  const latest = new Date(fyStart.getFullYear() + 1, fyStart.getMonth(), 0);
  return { min: toIsoDate(earliest), max: toIsoDate(latest), fyLabel: financialYearLabel(fyStart), earliest, latest };
}

function openReceiptPreview(file: File) {
  const url = URL.createObjectURL(file);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), RECEIPT_PREVIEW_LIFETIME_MS);
}

const EMPTY: FormState = { amount: "", category: "", date: "", description: "" };

type FormErrors = Partial<Record<keyof FormState | "receipt" | "submit", string>>;

export default function ExpenseFormModal({ onClose, onSaved }: Props) {
  const [form,         setForm]         = useState<FormState>(EMPTY);
  const [errors,       setErrors]       = useState<FormErrors>({});
  const [receiptFiles, setReceiptFiles] = useState<File[]>([]);
  const [submitting,   setSubmitting]   = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { data: fyConfig } = useFetch<{ financial_year_start_month: string }>(API.settings.financialYear);
  const dateWindow = fyConfig ? getExpenseDateWindow(fyConfig.financial_year_start_month) : null;

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
    if (!form.amount)                  errs.amount   = "Amount is required.";
    else if (Number(form.amount) <= 0) errs.amount   = "Amount must be greater than zero.";
    if (!form.category)                errs.category = "Please select a category.";
    if (!form.date) {
      errs.date = dateWindow
        ? `Enter a date between ${formatDateSlash(dateWindow.earliest)} and ${formatDateSlash(dateWindow.latest)}.`
        : "Date is required.";
    }
    if (receiptFiles.length === 0)     errs.receipt  = "At least one receipt is required.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setSubmitting(true);
    try {
      // The model's `title` field has no dedicated input in this form (the
      // real screen only asks for category/date/amount/purpose/receipt) —
      // the backend serializer allows it blank, so a short label derived
      // from the category and purpose is sent instead of leaving it empty.
      const category = form.category as ExpenseCategory;
      const derivedTitle = form.description.trim()
        ? form.description.trim().slice(0, 60)
        : CATEGORY_LABEL[category];

      const formData = new FormData();
      formData.append("title",        derivedTitle);
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
    <RequestModal
      title={<><i className="ti ti-wallet" style={{ marginRight: 8 }} />Expense claim</>}
      onClose={onClose}
      onSubmit={handleSubmit}
      submitting={submitting}
      error={errors.submit}
    >
          {/* Category + Date */}
          <div className="form-row cols-2 mb-16">
            <div className="field-group">
              <label className="field-label">
                Expense Category <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <select
                className={`field-input field-select${errors.category ? " field-error" : ""}`}
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
            <div className="field-group">
              <label className="field-label">
                Expense Date <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <DateInput
                className={`field-input${errors.date ? " field-error" : ""}`}
                value={form.date}
                min={dateWindow?.min}
                max={dateWindow?.max}
                onChange={isoDate => setField("date", isoDate)}
              />
              {errors.date
                ? <p className="field-error-msg">{errors.date}</p>
                : dateWindow && (
                  <p style={{ margin: "4px 0 0", fontSize: 11.5, color: "var(--on-variant)" }}>
                    {dateWindow.fyLabel}: allowed {formatDateSlash(dateWindow.earliest)} – {formatDateSlash(dateWindow.latest)}
                  </p>
                )}
            </div>
          </div>

          {/* Amount + Business purpose */}
          <div className="form-row cols-2 mb-16">
            <div className="field-group">
              <label className="field-label">
                Amount (₹) <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <input
                type="number"
                min="1"
                className={`field-input${errors.amount ? " field-error" : ""}`}
                placeholder="Amount"
                value={form.amount}
                onChange={e => setField("amount", e.target.value)}
              />
              {errors.amount && <p className="field-error-msg">{errors.amount}</p>}
            </div>
            <div className="field-group">
              <label className="field-label">Business purpose</label>
              <textarea
                className="field-input"
                rows={1}
                placeholder="Describe the business purpose"
                value={form.description}
                onChange={e => setField("description", e.target.value)}
                style={{ resize: "vertical" }}
              />
            </div>
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
                      onClick={() => openReceiptPreview(file)}
                      title="View receipt"
                      aria-label={`View receipt ${file.name}`}
                      style={{ background: "none", border: "none", cursor: "pointer", color: "var(--on-variant)", padding: 2 }}
                    >
                      <i className="ti ti-eye" />
                    </button>
                    <button
                      type="button"
                      onClick={() => removeReceipt(idx)}
                      aria-label={`Remove receipt ${file.name}`}
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
    </RequestModal>
  );
}
