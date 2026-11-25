import type { Metadata } from "next";
import "./globals.css";
import "./aira-theme.css";
import "./ess-theme.css";
import "./directory-theme.css";
import "./new-ui-bridge.css";
import "./themes.css";
import "./theme-styles.css";
import "./language-fonts.css";
import "./responsive.css";
// Self-hosted (not an external CDN) so every icon in the app doesn't
// depend on jsdelivr being reachable — imported (not a manual <link>) so
// Next.js bundles it and resolves its font url()s itself.
import "@tabler/icons-webfont/dist/tabler-icons.min.css";
import SessionExpiredOverlay from "@/components/SessionExpiredOverlay";
import VoiceCommandButton from "@/components/VoiceCommandButton";
import { ToastProvider } from "@/components/ToastProvider";
import { DialogProvider } from "@/components/DialogProvider";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";
import I18nProvider from "@/components/I18nProvider";
import { SCRIPT_FONT_CLASSES, interFont } from "@/lib/scriptFonts";

// The fonts live in the project (lib/fonts, see lib/scriptFonts.ts): nothing is downloaded from Google.

export const metadata: Metadata = {
  title: "Aira HRMS",
  description: "Aira Human Resource Management System — By SRIA",
  icons: {
    icon: [{ url: "/logo.svg", type: "image/svg+xml" }],
    shortcut: [{ url: "/logo.svg", type: "image/svg+xml" }],
    apple: [{ url: "/logo-icon.png", type: "image/png" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={SCRIPT_FONT_CLASSES} style={{ height: "100%" }} suppressHydrationWarning>
      <head>
        {/* Applies the saved theme before the first paint so there is no flash of the wrong colours. Kept in sync with lib/theme.ts. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
        <link rel="icon" type="image/svg+xml" href="/logo.svg" />
        <link rel="icon" type="image/png" href="/logo-icon.png" sizes="any" />
        <link rel="shortcut icon" href="/logo.svg" />
        <link rel="apple-touch-icon" href="/logo-icon.png" />
      </head>
      <body className={interFont.className} style={{ minHeight: "100vh" }} suppressHydrationWarning>
        <I18nProvider>
        <ToastProvider>
          <DialogProvider>
          {children}
          {/* Global floating action button — every authenticated page and
              every role. Disabled+tooltip when logged out elsewhere, hidden
              entirely on /login and /signup (see VoiceCommandButton.tsx).
              Lives here, not inside DashboardShell, so it isn't tied to the
              dashboard route tree or duplicated per role. */}
          <VoiceCommandButton />
          </DialogProvider>
        </ToastProvider>
        <SessionExpiredOverlay />
        </I18nProvider>
      </body>
    </html>
  );
}
