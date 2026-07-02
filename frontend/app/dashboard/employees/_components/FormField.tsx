"use client";

import type { FieldDef } from "../_data";

const BORDER     = "#d3dae8";
const BORDER_ERR = "#c0392b";

const INPUT =
  "w-full px-3.5 py-[7px] rounded-md border text-[13px] text-[var(--on-bg)] transition-all outline-none" +
  " bg-white placeholder:text-[#a5b0c2]" +
  " focus:border-[var(--primary)] focus:ring-2 focus:ring-[rgba(30,78,140,0.10)]";

/** Fixed label column width — keeps all inputs aligned */
const LABEL_W = "140px";

export default function FormField({
  field,
  value,
  onChange,
  disabled,
}: {
  field: FieldDef;
  value: string;
  onChange: (key: string, val: string) => void;
  disabled?: boolean;
}) {
  const set     = (v: string) => { if (!disabled) onChange(field.key, v); };
  const invalid = !disabled && field.required && field.type !== "readonly" && !value.trim();
  const borderColor = invalid ? BORDER_ERR : BORDER;

  return (
    /* Horizontal row: [label] [control]  — spans both columns when full=true */
    <div
      className="flex items-center gap-3"
      style={field.full ? { gridColumn: "1 / -1" } : undefined}
    >
      {/* Label — fixed width, right-aligned */}
      <label
        htmlFor={`fld-${field.key}`}
        className="text-right text-[12.5px] font-medium shrink-0 leading-tight"
        style={{
          width: LABEL_W,
          color: field.required ? "var(--primary)" : "var(--on-variant)",
        }}
      >
        {field.label}
        {field.required && (
          <span className="ml-0.5 font-bold" style={{ color: "var(--error)" }}>
            {" "}*
          </span>
        )}
      </label>

      {/* Control — takes remaining width */}
      <div className="flex-1 min-w-0">
        {renderControl()}
        {invalid && (
          <p className="text-[11px] mt-0.5" style={{ color: BORDER_ERR }}>
            {field.label} is required
          </p>
        )}
      </div>
    </div>
  );

  function renderControl() {
    switch (field.type) {
      case "readonly":
        return (
          <input
            id={`fld-${field.key}`}
            value={value || "—"}
            disabled
            suppressHydrationWarning
            className={INPUT + " cursor-not-allowed"}
            style={{ borderColor: BORDER, background: "#eff2f8", color: "#1e4e8c", fontWeight: 600 }}
          />
        );

      case "select":
        return (
          <select
            id={`fld-${field.key}`}
            value={value}
            onChange={(e) => set(e.target.value)}
            disabled={disabled}
            suppressHydrationWarning
            className={INPUT + " appearance-none pr-9" + (disabled ? " cursor-not-allowed" : " cursor-pointer")}
            style={{
              borderColor: disabled ? BORDER : borderColor,
              backgroundColor: disabled ? "#eff2f8" : undefined,
              backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>")`,
              backgroundRepeat: "no-repeat",
              backgroundPosition: "right 10px center",
              backgroundSize: "15px",
            }}
          >
            {field.options?.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        );

      case "radio":
        return (
          <div className="flex items-center gap-5 flex-wrap" style={{ minHeight: "36px" }}>
            {field.options?.map((o) => (
              <label
                key={o.value}
                className={"flex items-center gap-1.5 text-[13px] select-none" + (disabled ? " cursor-not-allowed opacity-70" : " cursor-pointer")}
                style={{ color: "var(--on-bg)" }}
              >
                <input
                  type="radio"
                  name={field.key}
                  value={o.value}
                  checked={value === o.value}
                  onChange={() => set(o.value)}
                  disabled={disabled}
                  suppressHydrationWarning
                  className={"w-4 h-4" + (disabled ? " cursor-not-allowed" : " cursor-pointer")}
                  style={{ accentColor: "var(--primary)" }}
                />
                {o.label}
              </label>
            ))}
          </div>
        );

      case "textarea":
        return (
          <textarea
            id={`fld-${field.key}`}
            value={value}
            rows={3}
            placeholder={field.placeholder}
            onChange={(e) => set(e.target.value)}
            disabled={disabled}
            suppressHydrationWarning
            className={INPUT + " resize-none" + (disabled ? " cursor-not-allowed" : "")}
            style={{ borderColor: disabled ? BORDER : borderColor, background: disabled ? "#eff2f8" : undefined }}
          />
        );

      case "date":
        return (
          <input
            id={`fld-${field.key}`}
            type="date"
            value={value}
            onChange={(e) => set(e.target.value)}
            disabled={disabled}
            suppressHydrationWarning
            className={INPUT + (disabled ? " cursor-not-allowed" : "")}
            style={{ borderColor: disabled ? BORDER : borderColor, background: disabled ? "#eff2f8" : undefined }}
          />
        );

      default:
        return (
          <input
            id={`fld-${field.key}`}
            type={
              field.type === "tel"    ? "tel"
              : field.type === "email"  ? "email"
              : field.type === "number" ? "number"
              : "text"
            }
            value={value}
            placeholder={field.placeholder}
            onChange={(e) => set(e.target.value)}
            disabled={disabled}
            suppressHydrationWarning
            className={INPUT + (disabled ? " cursor-not-allowed" : "")}
            style={{ borderColor: disabled ? BORDER : borderColor, background: disabled ? "#eff2f8" : undefined }}
          />
        );
    }
  }
}
