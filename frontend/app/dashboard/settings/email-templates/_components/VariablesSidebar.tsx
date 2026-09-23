"use client";

import { formatDateTime } from "@/lib/formatDate";
import type { ApiEmailTemplate } from "../_data";

interface Props {
  active: boolean;
  variables: string[];
  newTags: string[];
  onInsert: (tag: string) => void;
  isAddMode: boolean;
  template: ApiEmailTemplate | null;
}

export default function VariablesSidebar({ active, variables, newTags, onInsert, isAddMode, template }: Props) {
  return (
    <div className={`et-col-sidebar${active ? " et-tab-active" : ""}`} style={{ overflowY: "auto", background: "var(--bg-low)" }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "var(--outline)", letterSpacing: "0.08em", textTransform: "uppercase", padding: "14px 14px 10px" }}>
        Available Tags
      </div>

      {/* Predefined variables */}
      {variables.length > 0 && (
        <div style={{ padding: "0 10px 10px", display: "flex", flexDirection: "column", gap: 4 }}>
          {variables.map(v => {
            const tag = `{${v}}`;
            return (
              <button key={v} type="button" suppressHydrationWarning
                onClick={() => onInsert(tag)}
                title={`Insert ${tag}`}
                style={{ textAlign: "left", padding: "5px 9px", background: "rgba(124,58,237,0.06)", border: "1px solid rgba(124,58,237,0.12)", borderRadius: 4, fontSize: 11, fontFamily: "ui-monospace, monospace", color: "var(--primary)", cursor: "pointer" }}
                onMouseEnter={e => (e.currentTarget.style.background = "rgba(124,58,237,0.14)")}
                onMouseLeave={e => (e.currentTarget.style.background = "rgba(124,58,237,0.06)")}>
                {tag}
              </button>
            );
          })}
        </div>
      )}

      {/* Newly typed tags detected in subject/body */}
      {newTags.length > 0 && (
        <>
          <div style={{ fontSize: 10, fontWeight: 700, color: "var(--outline)", letterSpacing: "0.08em", textTransform: "uppercase", padding: "8px 14px 6px", borderTop: variables.length ? "1px solid var(--outline-v)" : "none" }}>
            Detected Tags
          </div>
          <div style={{ padding: "0 10px 14px", display: "flex", flexDirection: "column", gap: 4 }}>
            {newTags.map(v => {
              const tag = `{${v}}`;
              return (
                <button key={v} type="button" suppressHydrationWarning
                  onClick={() => onInsert(tag)}
                  title={`Insert ${tag}`}
                  style={{ textAlign: "left", padding: "5px 9px", background: "rgba(234,167,0,0.08)", border: "1px solid rgba(234,167,0,0.3)", borderRadius: 4, fontSize: 11, fontFamily: "ui-monospace, monospace", color: "#a06800", cursor: "pointer" }}
                  onMouseEnter={e => (e.currentTarget.style.background = "rgba(234,167,0,0.16)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "rgba(234,167,0,0.08)")}>
                  {tag}
                </button>
              );
            })}
          </div>
        </>
      )}

      {variables.length === 0 && newTags.length === 0 && (
        <div style={{ padding: "8px 14px 14px", fontSize: 12, color: "var(--on-variant)", lineHeight: 1.5 }}>
          Type <code style={{ fontSize: 11 }}>{"{VARIABLE}"}</code> in the subject or body to see tags here.
        </div>
      )}

      {/* Last updated */}
      {!isAddMode && template && (
        <div style={{ borderTop: "1px solid var(--outline-v)", padding: "12px 14px", fontSize: 11, color: "var(--outline)" }}>
          <div style={{ marginBottom: 2 }}>Last updated</div>
          <div style={{ color: "var(--on-variant)", fontWeight: 500 }}>
            {formatDateTime(template.updated_at)}
          </div>
          {template.is_builtin && (
            <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 5 }}>
              <i className="ti ti-shield-check" style={{ fontSize: 12, color: "var(--success)" }} />
              <span style={{ color: "var(--success)", fontWeight: 600, fontSize: 11 }}>Built-in template</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
