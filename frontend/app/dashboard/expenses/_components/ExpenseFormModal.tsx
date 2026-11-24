"use client";

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { formatDateSlash } from "@/lib/formatDate";
import { currentFinancialYearStart, financialYearLabel } from "@/app/dashboard/my-payslip/_components/types";
import RequestModal from "@/components/RequestModal";
import DateInput from "@/components/shared/DateInput";
import ExpenseCategoryPicker, { CATEGORIES, type ExpenseCategory } from "./ExpenseCategoryPicker";
import ExpenseReceiptPicker from "./ExpenseReceiptPicker";
import { ExpenseFormStyles } from "./expenseFormStyles";
import ExpenseFormStep from "./ExpenseFormStep";
import ExpenseClaimPreview from "./ExpenseClaimPreview";

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

const CATEGORY_LABEL: Record<ExpenseCategory, string> = Object.fromEntries(
  CATEGORIES.map(c => [c.value, c.label]),
) as Record<ExpenseCategory, string>;

// A bill may be dated up to this many months before the current financial year starts
// (the backend enforces the same window — EXPENSE_BACKDATE_MONTHS in hrms/serializers.py).
const BACKDATE_MONTHS = 4;

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

/** "Today" / "Yesterday" shortcuts, only when they fall inside the allowed window. */
function buildQuickDates(min: string, max: string): { label: string; iso: string }[] {
  const today = new Date();
  const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  return [{ label: "Today", iso: toIsoDate(today) }, { label: "Yesterday", iso: toIsoDate(yesterday) }].filter(quick => quick.iso >= min && quick.iso <= max);
}

function formatRupees(value: number): string {
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

const EMPTY: FormState = { amount: "", category: "", date: "", description: "" };

type FormErrors = Partial<Record<keyof FormState | "receipt" | "submit", string>>;

export default function ExpenseFormModal({ onClose, onSaved }: Props) {
  const t = useT();
  const [form,         setForm]         = useState<FormState>(EMPTY);
  const [errors,       setErrors]       = useState<FormErrors>({});
  const [receiptFiles, setReceiptFiles] = useState<File[]>([]);
  const [submitting,   setSubmitting]   = useState(false);
  const { data: fyConfig } = useFetch<{ financial_year_start_month: string }>(API.settings.financialYear);
  const dateWindow = fyConfig ? getExpenseDateWindow(fyConfig.financial_year_start_month) : null;

  const amount = Number(form.amount) > 0 ? Number(form.amount) : 0;
  const quickDates = dateWindow ? buildQuickDates(dateWindow.min, dateWindow.max) : [];

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
    setErrors(prev => ({ ...prev, [key]: undefined }));
  }

  function validate(): boolean {
    const errs: FormErrors = {};
    if (!form.amount)                  errs.amount   = t("Amount is required.");
    else if (Number(form.amount) <= 0) errs.amount   = t("Amount must be greater than zero.");
    if (!form.category)                errs.category = t("Please select a category.");
    if (!form.date) {
      errs.date = dateWindow
        ? t("Enter a date between {from} and {to}.", { from: formatDateSlash(dateWindow.earliest), to: formatDateSlash(dateWindow.latest) })
        : t("Date is required.");
    }
    if (receiptFiles.length === 0)     errs.receipt  = t("At least one receipt is required.");
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
          ?.response?.data?.message ?? t("Failed to submit expense. Please try again.");
      setErrors(prev => ({ ...prev, submit: msg }));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <RequestModal
      title={<><i className="ti ti-wallet" style={{ marginRight: 8 }} />{t("Expense claim")}</>}
      onClose={onClose}
      onSubmit={handleSubmit}
      submitting={submitting}
      error={errors.submit}
      maxWidth={980}
    >
          <ExpenseFormStyles />
          <div style={{ display: "flex", gap: 24, alignItems: "flex-start", flexWrap: "wrap" }}>
            <div style={{ flex: "2 1 420px", minWidth: 0 }}>
              <ExpenseFormStep number={1} title={t("What was it for?")} hint={t("Pick the kind of expense.")} done={Boolean(form.category)}>
                <ExpenseCategoryPicker value={form.category} hasError={Boolean(errors.category)} onChange={category => setField("category", category)} />
                {errors.category && <p className="field-error-msg">{errors.category}</p>}
              </ExpenseFormStep>

              <ExpenseFormStep number={2} title={t("When and how much?")} hint={t("The date on the bill and the amount you paid.")} done={Boolean(form.date) && amount > 0}>
                <div className="form-row cols-2">
                  <div className="field-group">
                    <label className="field-label">{t("Expense Date")} <span style={{ color: "var(--error)" }}>*</span></label>
                    <DateInput
                      className={`field-input${errors.date ? " field-error" : ""}`}
                      value={form.date}
                      min={dateWindow?.min}
                      max={dateWindow?.max}
                      onChange={isoDate => setField("date", isoDate)}
                    />
                    <div className="xf-quick">
                      {quickDates.map(quick => (
                        <button key={quick.label} type="button" onClick={() => setField("date", quick.iso)}>{t(quick.label)}</button>
                      ))}
                    </div>
                    {errors.date
                      ? <p className="field-error-msg">{errors.date}</p>
                      : dateWindow && (
                        <p className="xf-words">
                          {t("{label}: allowed {from} – {to}", { label: dateWindow.fyLabel, from: formatDateSlash(dateWindow.earliest), to: formatDateSlash(dateWindow.latest) })}
                        </p>
                      )}
                  </div>
                  <div className="field-group">
                    <label className="field-label">{t("Amount")} <span style={{ color: "var(--error)" }}>*</span></label>
                    <div className="xf-money">
                      <b>₹</b>
                      <input
                        type="number"
                        min="1"
                        inputMode="decimal"
                        className={`field-input${errors.amount ? " field-error" : ""}`}
                        placeholder="0"
                        value={form.amount}
                        onChange={e => setField("amount", e.target.value)}
                      />
                    </div>
                    {errors.amount
                      ? <p className="field-error-msg">{errors.amount}</p>
                      : amount > 0 && <p className="xf-words">{formatRupees(amount)}</p>}
                  </div>
                </div>
              </ExpenseFormStep>

              <ExpenseFormStep number={3} title={t("Why was it needed?")} hint={t("Optional, but it helps your approver decide faster.")}>
                <textarea
                  className="field-input"
                  rows={3}
                  placeholder={t("Describe the business purpose")}
                  value={form.description}
                  onChange={e => setField("description", e.target.value)}
                  style={{ resize: "vertical", width: "100%" }}
                />
              </ExpenseFormStep>

              <ExpenseFormStep number={4} title={t("Attach your receipts")} hint={t("PDF, JPG or PNG, up to 5 MB each. At least one is required.")} done={receiptFiles.length > 0}>
                <ExpenseReceiptPicker
                  files={receiptFiles}
                  error={errors.receipt}
                  onChange={setReceiptFiles}
                  onError={message => setErrors(prev => ({ ...prev, receipt: message }))}
                />
              </ExpenseFormStep>
            </div>

            <div style={{ flex: "1 1 260px", minWidth: 0, position: "sticky", top: 0 }}>
              <ExpenseClaimPreview
                category={form.category}
                categoryLabel={form.category ? t(CATEGORY_LABEL[form.category]) : null}
                amount={amount}
                dateLabel={form.date ? formatDateSlash(new Date(`${form.date}T00:00:00`)) : null}
                purpose={form.description}
                receiptCount={receiptFiles.length}
              />
            </div>
          </div>
    </RequestModal>
  );
}
