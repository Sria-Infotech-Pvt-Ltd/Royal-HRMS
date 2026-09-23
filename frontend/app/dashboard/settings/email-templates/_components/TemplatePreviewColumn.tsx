"use client";

import DOMPurify from "dompurify";

// Highlight {VARIABLE} tokens with a coloured span, and sanitize — this
// renders straight into the DOM via dangerouslySetInnerHTML below, and a
// saved template's subject/body can have been authored by a different
// admin (or pasted from an external source) at any point in the past, so
// it's stored, not-necessarily-trusted HTML like any other.
function highlightVars(html: string): string {
  const withHighlights = html.replace(
    /\{([A-Za-z][A-Za-z0-9_]*)\}/g,
    '<span style="background:rgba(234,167,0,0.18);color:#a06800;padding:1px 5px;border-radius:3px;font-family:ui-monospace,monospace;font-size:0.88em;font-weight:600">{$1}</span>'
  );
  return DOMPurify.sanitize(withHighlights);
}

export default function TemplatePreviewColumn({ subject, body, active }: { subject: string; body: string; active: boolean }) {
  return (
    <div className={`et-col-preview${active ? " et-tab-active" : ""}`} style={{ overflowY: "auto", borderRight: "1px solid var(--outline-v)", background: "#fafbfc", display: "flex", flexDirection: "column" }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "var(--outline)", letterSpacing: "0.08em", textTransform: "uppercase", padding: "14px 14px 10px", flexShrink: 0 }}>
        Live Preview
      </div>
      <div style={{ padding: "0 14px 16px", flex: 1, overflowY: "auto" }}>
        {/* Subject preview */}
        <div style={{ fontSize: 10, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Subject</div>
        <div style={{ fontSize: 12, color: "var(--on-bg)", marginBottom: 14, padding: "8px 10px", background: "var(--surface)", borderRadius: 6, border: "1px solid var(--outline-v)", lineHeight: 1.5, wordBreak: "break-word" }}
          dangerouslySetInnerHTML={{ __html: highlightVars(subject) || '<span style="color:var(--outline);font-style:italic">No subject yet…</span>' }} />

        {/* Body preview */}
        <div style={{ fontSize: 10, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Body</div>
        {body ? (
          <div style={{ fontSize: 12, lineHeight: 1.75, padding: "12px 12px", background: "var(--surface)", borderRadius: 6, border: "1px solid var(--outline-v)", wordBreak: "break-word", overflowX: "auto" }}
            dangerouslySetInnerHTML={{ __html: highlightVars(body) }} />
        ) : (
          <div style={{ fontSize: 12, color: "var(--outline)", fontStyle: "italic", padding: "12px 12px", background: "var(--surface)", borderRadius: 6, border: "1px solid var(--outline-v)" }}>
            Body will appear here…
          </div>
        )}
      </div>
    </div>
  );
}
