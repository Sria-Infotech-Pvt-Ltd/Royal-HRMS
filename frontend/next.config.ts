import type { NextConfig } from "next";

// Destination for the /api/* proxy, called server-side by the Next.js
// process itself - NOT the same thing as the public origin the browser
// talks to. In local dev there's no reverse proxy in front of anything, so
// NEXT_PUBLIC_API_URL (e.g. http://localhost:8000) happens to be correct for
// both. In production, Nginx sits in front of both this Next.js server and
// Django, and NEXT_PUBLIC_API_URL is the public https://<domain> the browser
// uses - if this rewrite also targeted that public origin, the request would
// round-trip back out through Nginx and land on this same Next.js server
// again instead of reaching Django, looping forever. INTERNAL_API_URL (server
// env only, never NEXT_PUBLIC_-prefixed so it's never sent to the browser)
// must be set to Django's direct address (e.g. http://127.0.0.1:8003) in any
// environment that sits behind a reverse proxy.
const API_HOST =
  process.env.INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Pins the workspace root to this directory. Without this, Turbopack walks
  // up looking for lockfiles and finds the repo-root package-lock.json above
  // frontend/ too, so it guesses the wrong root and warns on every dev/build.
  turbopack: {
    root: __dirname,
  },
  // Prevent Next.js from 308-redirecting /api/login/ → /api/login before the
  // rewrite runs. Without this, Django's APPEND_SLASH raises a RuntimeError on
  // POST because it cannot redirect and preserve the request body.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_HOST}/api/:path*/`,
      },
    ];
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "res.cloudinary.com",
      },
      {
        // Actual media provider (see backend .env.example IMAGEKIT_* vars) -
        // without this, next/image refuses to render any uploaded file.
        protocol: "https",
        hostname: "ik.imagekit.io",
      },
    ],
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options",           value: "DENY" },
          { key: "X-Content-Type-Options",     value: "nosniff" },
          { key: "Referrer-Policy",            value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
