import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import "./globals.css";
import SessionExpiredOverlay from "@/components/SessionExpiredOverlay";
import VoiceCommandButton from "@/components/VoiceCommandButton";
import { ToastProvider } from "@/components/ToastProvider";

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Royal HRMS",
  description: "Royal Human Resource Management System — By SRIA",
  icons: {
    icon: [{ url: "/logo.svg", type: "image/svg+xml" }],
    shortcut: [{ url: "/logo.svg", type: "image/svg+xml" }],
    apple: [{ url: "/logo.png", type: "image/png" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" style={{ height: "100%" }} suppressHydrationWarning>
      <head>
        <link rel="icon" type="image/svg+xml" href="/logo.svg" />
        <link rel="icon" type="image/png" href="/logo.png" sizes="any" />
        <link rel="shortcut icon" href="/logo.svg" />
        <link rel="apple-touch-icon" href="/logo.png" />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css"
        />
      </head>
      <body className={poppins.className} style={{ minHeight: "100vh" }} suppressHydrationWarning>
        <ToastProvider>
          {children}
          {/* Global floating action button — every authenticated page and
              every role. Disabled+tooltip when logged out elsewhere, hidden
              entirely on /login and /signup (see VoiceCommandButton.tsx).
              Lives here, not inside DashboardShell, so it isn't tied to the
              dashboard route tree or duplicated per role. */}
          <VoiceCommandButton />
        </ToastProvider>
        <SessionExpiredOverlay />
      </body>
    </html>
  );
}
