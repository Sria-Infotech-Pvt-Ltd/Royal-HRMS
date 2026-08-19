const SETTINGS_LINKS = [
  {
    href: "/platform-admin/audit-log",
    icon: "ti-history",
    title: "Audit Log",
    description: "Every platform-admin action — who created or changed a company, and when.",
  },
  {
    href: "/platform-admin/email-settings",
    icon: "ti-mail",
    title: "Email Settings",
    description: "The platform's own outbound mail account, used for provisioning and password-reset emails.",
  },
  {
    href: "/platform-admin/account",
    icon: "ti-user-circle",
    title: "My Account",
    description: "Change your own platform-admin password.",
  },
];

export default function SettingsHubPage() {
  return (
    <div style={{ padding: "32px 24px" }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 24 }}>Settings</h1>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
        {SETTINGS_LINKS.map(link => (
          <a
            key={link.href}
            href={link.href}
            className="card"
            style={{ display: "block", textDecoration: "none", color: "inherit" }}
          >
            <div className="card-body">
              <div
                style={{
                  width: 36, height: 36, borderRadius: 8, background: "rgba(30, 78, 140, 0.1)",
                  display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 12,
                }}
              >
                <i className={`ti ${link.icon}`} style={{ fontSize: 17, color: "var(--primary)" }} />
              </div>
              <h2 style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{link.title}</h2>
              <p style={{ fontSize: 12.5, color: "var(--on-variant)", lineHeight: 1.5 }}>{link.description}</p>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
