interface Props {
  icon:        string;
  title:       string;
  description: string;
  features?:   string[];
}

export default function ComingSoon({ icon, title, description, features }: Props) {
  return (
    <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ width: "100%", maxWidth: 520, textAlign: "center" }}>

        {/* Icon bubble */}
        <div style={{
          width: 80, height: 80, borderRadius: "50%",
          background: "linear-gradient(135deg, color-mix(in srgb, var(--brand) 10%, transparent) 0%, color-mix(in srgb, var(--brand) 6%, transparent) 100%)",
          border: "1.5px solid color-mix(in srgb, var(--brand) 15%, transparent)",
          display: "flex", alignItems: "center", justifyContent: "center",
          margin: "0 auto 24px",
        }}>
          <i className={`ti ${icon}`} style={{ fontSize: 34, color: "var(--primary)" }} />
        </div>

        {/* Badge */}
        <div style={{ marginBottom: 14, display: "flex", justifyContent: "center" }}>
          <span style={{
            fontSize: 11, fontWeight: 700, letterSpacing: "0.08em",
            background: "color-mix(in srgb, var(--brand) 8%, transparent)", color: "var(--primary)",
            padding: "4px 12px", borderRadius: 20,
            border: "1px solid color-mix(in srgb, var(--brand) 18%, transparent)",
          }}>
            COMING SOON
          </span>
        </div>

        <h2 style={{ fontSize: 22, fontWeight: 700, color: "var(--on-bg)", marginBottom: 10 }}>
          {title}
        </h2>
        <p style={{ fontSize: 14, color: "var(--on-variant)", lineHeight: 1.6, marginBottom: features ? 28 : 0 }}>
          {description}
        </p>

        {/* Feature preview list */}
        {features && features.length > 0 && (
          <div style={{
            background: "var(--bg-low)",
            border: "1px solid var(--outline-v)",
            borderRadius: 14,
            padding: "20px 24px",
            textAlign: "left",
          }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: "var(--outline)", letterSpacing: "0.06em", marginBottom: 12 }}>
              PLANNED FEATURES
            </p>
            {features.map(f => (
              <div key={f} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, fontSize: 13, color: "var(--on-variant)" }}>
                <i className="ti ti-circle-check" style={{ color: "var(--primary)", fontSize: 15, flexShrink: 0 }} />
                {f}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
